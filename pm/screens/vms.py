"""Tela de gerenciamento de VMs com modais de formulário."""
from __future__ import annotations
from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import DataTable, Button, Label, Input, Select, Static
from textual.containers import Horizontal, Vertical, ScrollableContainer
from textual import work

from pm.data import VM, load_vms, load_domains, add_vm, update_vm, delete_vm, get_vm
from pm.nginx import generate_nginx, reload_nginx


# ── Modal: Wizard de Nova VM (2 etapas) ──────────────────────────────────────

class VMWizardModal(ModalScreen[VM | None]):
    """Wizard de criação de VM em 2 etapas."""

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-form", id="vm-wizard"):
            yield Label("Nova VM", classes="modal-title")
            yield Static("[dim]Etapa 1 de 2 — Identificação[/]", id="wizard-step-label")

            # ── Etapa 1 ──────────────────────────────────────
            with Vertical(id="step-1"):
                yield Label("Nome (sem espaços):")
                yield Input(placeholder="ex: docker-apps", id="f-nome")
                yield Label("Descrição:")
                yield Input(placeholder="ex: Docker Apps", id="f-desc")
                yield Label("IP interno:")
                yield Input(placeholder="192.168.1.x", id="f-ip", value="192.168.1.")
                with Horizontal(classes="modal-footer"):
                    yield Button("Cancelar",  id="btn-cancel", variant="default")
                    yield Button("Próximo →", id="btn-next",   variant="primary")

            # ── Etapa 2 ──────────────────────────────────────
            with Vertical(id="step-2"):
                yield Label("Modo SSL:")
                yield Select(
                    [("passthrough — VM tem proxy próprio (Traefik, Caddy)", "passthrough"),
                     ("termination — Porteiro gera SSL via Certbot",         "termination")],
                    value="passthrough", id="f-modo",
                )
                # HTTP on/off: apenas relevante para Passthrough.
                # No Termination, HTTP fica sempre ON (Certbot + redirect para HTTPS).
                with Vertical(id="container-http"):
                    yield Label("HTTP (porta 80):")
                    yield Select(
                        [("on  — encaminhar HTTP", "on"), ("off — bloquear HTTP", "off")],
                        value="on", id="f-http-on",
                    )
                # HTTPS é sempre ON — não há seletor
                yield Static(
                    "[dim]HTTPS (porta 443): sempre ✔ ativo[/]",
                    id="label-https-always-on"
                )
                with Horizontal(classes="modal-footer"):
                    yield Button("← Voltar",  id="btn-back",  variant="default")
                    yield Button("Testar",    id="btn-test",  variant="primary")
                    yield Button("Finalizar", id="btn-save",  variant="success")

    def on_mount(self) -> None:
        self._show_step(1)

    def _show_step(self, step: int) -> None:
        self.query_one("#step-1").display = (step == 1)
        self.query_one("#step-2").display = (step == 2)
        label = "Etapa 1 de 2 — Identificação" if step == 1 else "Etapa 2 de 2 — Configuração de Rede"
        self.query_one("#wizard-step-label", Static).update(f"[dim]{label}[/]")
        self._step = step
        if step == 2:
            self._update_http_visibility()

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "f-modo":
            self._update_http_visibility()

    def _update_http_visibility(self) -> None:
        """Mostra o seletor HTTP apenas para modo passthrough."""
        try:
            modo = self.query_one("#f-modo", Select).value
            self.query_one("#container-http").display = (modo == "passthrough")
        except Exception:
            pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id

        if bid == "btn-cancel":
            self.dismiss(None)

        elif bid == "btn-next":
            nome = self.query_one("#f-nome", Input).value.strip()
            ip   = self.query_one("#f-ip",   Input).value.strip()
            if not nome or " " in nome:
                self.app.notify("Nome inválido — sem espaços.", severity="warning")
                self.query_one("#f-nome", Input).focus()
                return
            if not ip:
                self.app.notify("Preencha o IP interno.", severity="warning")
                self.query_one("#f-ip", Input).focus()
                return
            all_vms = load_vms()
            if any(v.nome == nome for v in all_vms):
                self.app.notify(f"A VM '{nome}' já existe.", severity="error")
                self.query_one("#f-nome", Input).focus()
                return
            if any(v.ip == ip for v in all_vms):
                other = next(v.nome for v in all_vms if v.ip == ip)
                self.app.notify(f"O IP {ip} já está em uso pela VM '{other}'.", severity="error")
                self.query_one("#f-ip", Input).focus()
                return
            self._show_step(2)

        elif bid == "btn-back":
            self._show_step(1)

        elif bid == "btn-test":
            ip = self.query_one("#f-ip", Input).value.strip()
            if ip:
                self.test_connectivity(ip, "443")

        elif bid == "btn-save":
            nome  = self.query_one("#f-nome", Input).value.strip()
            desc  = self.query_one("#f-desc", Input).value.strip()
            ip    = self.query_one("#f-ip",   Input).value.strip()
            modo  = self.query_one("#f-modo", Select).value
            # HTTP: configurável apenas no passthrough; termination sempre ON
            if modo == "passthrough":
                http_on = self.query_one("#f-http-on", Select).value
            else:
                http_on = "on"
            https_on = "on"  # HTTPS sempre ativo
            self.dismiss(VM(nome, ip, "80", "443", http_on, https_on, modo, desc))

    @work(exclusive=True)
    async def test_connectivity(self, ip: str, port: str) -> None:
        self.app.notify(f"Testando conectividade com {ip}...", severity="information")
        import asyncio
        proc = await asyncio.create_subprocess_exec(
            "ping", "-c", "1", "-W", "2", ip,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL
        )
        await proc.communicate()
        if proc.returncode != 0:
            self.app.notify(f"❌ Falha no Ping: {ip} está inatingível.", severity="error")
            return
        try:
            p = int(port)
            reader, writer = await asyncio.wait_for(asyncio.open_connection(ip, p), timeout=2.0)
            writer.close()
            await writer.wait_closed()
            self.app.notify(f"✔ Sucesso! Ping OK e porta {p} aberta em {ip}.", severity="information")
        except Exception:
            self.app.notify(f"⚠ Ping OK em {ip}, mas a porta {port} parece fechada.", severity="warning")


# ── Modal: Editar VM (página única) ──────────────────────────────────────────

class VMFormModal(ModalScreen[VM | None]):
    """Modal para editar uma VM existente."""

    def __init__(self, vm: VM) -> None:
        super().__init__()
        self._vm = vm

    def compose(self) -> ComposeResult:
        vm = self._vm
        with Vertical(classes="modal-form"):
            yield Label(f"Editar VM: {vm.nome}", classes="modal-title")
            yield Label("IP interno:")
            yield Input(placeholder="192.168.1.x", id="f-ip", value=vm.ip)
            yield Label("Modo SSL:")
            yield Select(
                [("passthrough — VM tem proxy próprio (Traefik, Caddy)", "passthrough"),
                 ("termination — Porteiro gera SSL via Certbot",         "termination")],
                value=vm.modo, id="f-modo",
            )
            # HTTP on/off: apenas para passthrough
            with Vertical(id="container-http"):
                yield Label("HTTP (porta 80):")
                yield Select(
                    [("on  — encaminhar HTTP", "on"), ("off — bloquear HTTP", "off")],
                    value=vm.http_on, id="f-http-on",
                )
            yield Static("[dim]HTTPS (porta 443): sempre ✔ ativo[/]", id="label-https")
            yield Label("Descrição:")
            yield Input(placeholder="ex: Docker Apps", id="f-desc", value=vm.descricao)
            with Horizontal(classes="modal-footer"):
                yield Button("Testar",   variant="primary", id="btn-test")
                yield Button("Salvar",   variant="success", id="btn-save")
                yield Button("Cancelar", id="btn-cancel")

    def on_mount(self) -> None:
        self._update_http_visibility()

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "f-modo":
            self._update_http_visibility()

    def _update_http_visibility(self) -> None:
        try:
            modo = self.query_one("#f-modo", Select).value
            self.query_one("#container-http").display = (modo == "passthrough")
        except Exception:
            pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel":
            self.dismiss(None)
            return
        if event.button.id == "btn-test":
            ip = self.query_one("#f-ip", Input).value.strip()
            if ip:
                self.test_connectivity(ip, "443")
            return
        vm   = self._vm
        ip   = self.query_one("#f-ip",   Input).value.strip()
        modo = self.query_one("#f-modo", Select).value
        desc = self.query_one("#f-desc", Input).value.strip()
        if not ip:
            self.app.notify("Preencha o IP interno.", severity="warning")
            self.query_one("#f-ip", Input).focus()
            return
        all_vms = load_vms()
        if any(v.ip == ip and v.nome != vm.nome for v in all_vms):
            other = next(v.nome for v in all_vms if v.ip == ip)
            self.app.notify(f"O IP {ip} já está em uso pela VM '{other}'.", severity="error")
            self.query_one("#f-ip", Input).focus()
            return
        # HTTP: configurável apenas no passthrough
        if modo == "passthrough":
            http_on = self.query_one("#f-http-on", Select).value
        else:
            http_on = "on"
        https_on = "on"
        self.dismiss(VM(vm.nome, ip, vm.porta_http, vm.porta_https, http_on, https_on, modo, desc))

    @work(exclusive=True)
    async def test_connectivity(self, ip: str, port: str) -> None:
        self.app.notify(f"Testando conectividade com {ip}...", severity="information")
        import asyncio
        proc = await asyncio.create_subprocess_exec(
            "ping", "-c", "1", "-W", "2", ip,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL
        )
        await proc.communicate()
        if proc.returncode != 0:
            self.app.notify(f"❌ Falha no Ping: {ip} está inatingível.", severity="error")
            return
        try:
            p = int(port)
            reader, writer = await asyncio.wait_for(asyncio.open_connection(ip, p), timeout=2.0)
            writer.close()
            await writer.wait_closed()
            self.app.notify(f"✔ Sucesso! Ping OK e porta {p} aberta em {ip}.", severity="information")
        except Exception:
            self.app.notify(f"⚠ Ping OK em {ip}, mas a porta {port} parece fechada.", severity="warning")


# ── Modal: Domínios da VM ────────────────────────────────────────────────────

class VMDomainsModal(ModalScreen[None]):
    """Exibe os domínios vinculados a uma VM."""

    def __init__(self, vm: VM) -> None:
        super().__init__()
        self._vm = vm

    def compose(self) -> ComposeResult:
        vm = self._vm
        domains = [d for d in load_domains() if d.vm_nome == vm.nome]
        with Vertical(classes="modal-form"):
            yield Label(
                f"🌐 Domínios vinculados — {vm.nome} ({vm.ip})",
                classes="modal-title"
            )
            yield Static(
                f"[dim]Modo: {vm.modo.upper()} | HTTP: {'✔' if vm.http_on == 'on' else '❌'} | HTTPS: ✔[/]"
            )
            if not domains:
                yield Static("[dim]  Nenhum domínio vinculado a esta VM.[/]")
            else:
                yield DataTable(id="vm-domains-table", cursor_type="row")
            with Horizontal(classes="modal-footer"):
                yield Button("Fechar", variant="primary", id="btn-close")

    def on_mount(self) -> None:
        domains = [d for d in load_domains() if d.vm_nome == self._vm.nome]
        if not domains:
            return
        t = self.query_one("#vm-domains-table", DataTable)
        t.add_columns("Domínio", "Backend", "SSL")
        for d in domains:
            ssl = "[green]✔ OK[/]" if d.has_cert else (
                "[red]sem cert[/]" if self._vm.modo == "termination" else "[dim]n/a[/]"
            )
            bp = d.backend_port or "-"
            t.add_row(d.dominio, bp, ssl)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(None)


# ── Modal: Confirmar exclusão ─────────────────────────────────────────────────

class ConfirmDeleteModal(ModalScreen[bool]):
    def __init__(self, msg: str) -> None:
        super().__init__()
        self._msg = msg

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-form"):
            yield Label("⚠  Confirmar exclusão", classes="modal-title")
            yield Static(self._msg)
            with Horizontal(classes="modal-footer"):
                yield Button("Excluir", variant="error", id="btn-yes")
                yield Button("Cancelar", id="btn-no")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "btn-yes")


# ── Modal: Confirmação genérica (label e variante customizáveis) ─────────────────

class ConfirmActionModal(ModalScreen[bool]):
    def __init__(self, title: str, msg: str,
                 confirm_label: str = "Confirmar",
                 confirm_variant: str = "warning") -> None:
        super().__init__()
        self._title          = title
        self._msg            = msg
        self._confirm_label  = confirm_label
        self._confirm_variant = confirm_variant

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-form"):
            yield Label(self._title, classes="modal-title")
            yield Static(self._msg)
            with Horizontal(classes="modal-footer"):
                yield Button(self._confirm_label, variant=self._confirm_variant, id="btn-yes")
                yield Button("Cancelar", id="btn-no")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "btn-yes")



# ── Tela principal de VMs ─────────────────────────────────────────────────────

class VMsScreen(Vertical):

    def compose(self) -> ComposeResult:
        with Horizontal(classes="toolbar"):
            yield Button("＋ Nova VM",    id="btn-add",     classes="btn-add")
            yield Button("✎ Editar",      id="btn-edit",    classes="btn-edit")
            yield Button("✕ Excluir",     id="btn-delete",  classes="btn-delete")
            yield Button("⇄ Portas",      id="btn-ports",   classes="btn-apply")
            yield Button("🌐 Domínios",   id="btn-domains", classes="btn-apply")
            yield Button("⏯ Ativar/Pausar", id="btn-toggle", classes="btn-edit")
        yield DataTable(id="vms-table", cursor_type="row")
        yield Static("", id="vm-status-bar", classes="muted-text")

    def on_mount(self) -> None:
        t = self.query_one("#vms-table", DataTable)
        t.add_columns("Status", "Nome", "IP", "HTTP", "HTTPS", "Modo", "Desc", "Doms")
        self.refresh_table()

    def refresh_table(self) -> None:
        t = self.query_one("#vms-table", DataTable)
        t.clear()
        vms     = load_vms()
        domains = load_domains()
        for vm in vms:
            dom_count = sum(1 for d in domains if d.vm_nome == vm.nome)
            h = "✔" if vm.http_on  == "on" else "❌"
            s = "✔"  # HTTPS sempre ativo
            modo_disp = (
                "[cyan]TERMINATION[/]" if vm.modo == "termination"
                else "[dim]PASSTHROUGH[/]"
            )
            status = "[green]● Ativo[/]" if vm.ativo == "on" else "[red]○ Inativo[/]"
            t.add_row(status, vm.nome, vm.ip, h, s, modo_disp, vm.descricao, str(dom_count),
                      key=vm.nome)
        bar = self.query_one("#vm-status-bar", Static)
        bar.update(f"  {len(vms)} VM(s) cadastrada(s)")

    def _selected_vm_name(self) -> str | None:
        t = self.query_one("#vms-table", DataTable)
        if t.row_count == 0:
            return None
        row = t.get_row_at(t.cursor_row)
        # Status agora é a coluna 0, Nome é a coluna 1
        return str(row[1]) if row else None

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-add":
            self.app.push_screen(VMWizardModal(), self._on_add)
        elif event.button.id == "btn-edit":
            nome = self._selected_vm_name()
            if nome:
                vm = get_vm(nome)
                if vm:
                    self.app.push_screen(VMFormModal(vm), self._on_edit)
            else:
                self.app.notify("Selecione uma VM para editar.", severity="warning")

        elif event.button.id == "btn-delete":
            nome = self._selected_vm_name()
            if nome:
                doms = [d.dominio for d in load_domains() if d.vm_nome == nome]
                msg  = f"Excluir a VM '[bold]{nome}[/]'?"
                if doms:
                    msg += f"\n\n[yellow]Aviso: {len(doms)} domínio(s) ficarão órfãos.[/]"
                self.app.push_screen(ConfirmDeleteModal(msg), lambda ok: self._on_delete(ok, nome))
            else:
                self.app.notify("Selecione uma VM para excluir.", severity="warning")

        elif event.button.id == "btn-ports":
            nome = self._selected_vm_name()
            if nome:
                vm = get_vm(nome)
                if vm and vm.modo == "passthrough":
                    self.app.push_screen(PortsModal(nome), self._on_ports)
                elif vm and vm.modo == "termination":
                    self.app.notify(
                        "VMs em modo Termination sempre recebem HTTP (Certbot) e HTTPS.",
                        severity="information"
                    )
            else:
                self.app.notify("Selecione uma VM para gerenciar portas.", severity="warning")

        elif event.button.id == "btn-domains":
            nome = self._selected_vm_name()
            if nome:
                vm = get_vm(nome)
                if vm:
                    self.app.push_screen(VMDomainsModal(vm))
            else:
                self.app.notify("Selecione uma VM para ver os domínios.", severity="warning")

        elif event.button.id == "btn-toggle":
            nome = self._selected_vm_name()
            if nome:
                vm = get_vm(nome)
                if vm:
                    if vm.ativo == "on":
                        # Desativar: pede confirmação
                        doms = [d.dominio for d in load_domains() if d.vm_nome == nome]
                        msg  = f"Tem certeza que deseja [bold]desativar[/] a VM '[bold]{nome}[/]'?\n"
                        msg += "\n[yellow]O NGINX será recarregado e esta VM deixará de receber tráfego.[/]"
                        if doms:
                            msg += f"\n\n[dim]Domínios afetados: {', '.join(doms)}[/]"
                        self.app.push_screen(
                            ConfirmActionModal(
                                title="⏸ Desativar VM",
                                msg=msg,
                                confirm_label="Desativar",
                                confirm_variant="error",
                            ),
                            lambda ok, v=vm: self._on_toggle_confirm(ok, v, "off")
                        )
                    else:
                        # Ativar: pede confirmação
                        doms = [d.dominio for d in load_domains() if d.vm_nome == nome]
                        msg  = f"Tem certeza que deseja [bold]ativar[/] a VM '[bold]{nome}[/]'?\n"
                        msg += "\n[green]O NGINX será recarregado e os domínios voltam a receber tráfego.[/]"
                        if doms:
                            msg += f"\n\n[dim]Domínios que voltam: {', '.join(doms)}[/]"
                        self.app.push_screen(
                            ConfirmActionModal(
                                title="▶ Ativar VM",
                                msg=msg,
                                confirm_label="Ativar",
                                confirm_variant="success",
                            ),
                            lambda ok, v=vm: self._on_toggle_confirm(ok, v, "on")
                        )
            else:
                self.app.notify("Selecione uma VM para ativar/pausar.", severity="warning")

    def _on_add(self, vm: VM | None) -> None:
        if vm:
            add_vm(vm)
            self.refresh_table()

    def _on_edit(self, vm: VM | None) -> None:
        if vm:
            update_vm(vm)
            self.refresh_table()

    def _on_delete(self, ok: bool, nome: str) -> None:
        if ok:
            delete_vm(nome)
            self.refresh_table()

    def _on_ports(self, _: None) -> None:
        self.refresh_table()

    def _on_toggle_confirm(self, ok: bool, vm: VM, novo_estado: str) -> None:
        """Callback da confirmação de ativar/desativar: salva, gera NGINX e recarrega."""
        if not ok:
            return
        vm.ativo = novo_estado
        update_vm(vm)
        self.refresh_table()
        acao_msg = "desativada" if novo_estado == "off" else "reativada"
        self.app.notify(f"VM '{vm.nome}' {acao_msg}. Aplicando NGINX...", severity="warning")
        import threading
        threading.Thread(target=self._thread_nginx_reload, args=(vm.nome, acao_msg), daemon=True).start()

    def _thread_nginx_reload(self, nome: str, acao: str = "atualizada") -> None:
        generate_nginx()
        ok, err = reload_nginx()
        if ok:
            self.app.call_from_thread(
                self.app.notify,
                f"✔ NGINX recarregado — VM '{nome}' {acao}.",
                severity="information"
            )
        else:
            self.app.call_from_thread(
                self.app.notify,
                f"❌ Erro ao recarregar NGINX: {err[:100]}",
                severity="error"
            )


# ── Modal: Ativar/Desativar portas (apenas Passthrough) ──────────────────────

class PortsModal(ModalScreen[None]):
    def __init__(self, nome: str) -> None:
        super().__init__()
        self._nome = nome

    def compose(self) -> ComposeResult:
        vm = get_vm(self._nome)
        with Vertical(classes="modal-form"):
            yield Label(f"Portas — {self._nome} ({vm.ip if vm else ''})",
                        classes="modal-title")
            yield Static("[dim]HTTPS (443): sempre ✔ ativo[/]")
            yield Label("HTTP (porta 80):")
            yield Select(
                [("on — encaminhar HTTP", "on"), ("off — bloquear HTTP", "off")],
                value=vm.http_on if vm else "on", id="p-http",
            )
            with Horizontal(classes="modal-footer"):
                yield Button("Salvar", variant="success", id="btn-save")
                yield Button("Cancelar", id="btn-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel":
            self.dismiss(None)
            return
        vm = get_vm(self._nome)
        if vm:
            vm.http_on  = self.query_one("#p-http", Select).value
            vm.https_on = "on"  # sempre ON
            update_vm(vm)
        self.dismiss(None)
