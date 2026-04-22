"""Tela de gerenciamento de VMs com modais de formulário."""
from __future__ import annotations
from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import DataTable, Button, Label, Input, Select, Static
from textual.containers import Horizontal, Vertical, ScrollableContainer
from textual import work

from pm.data import VM, load_vms, load_domains, add_vm, update_vm, delete_vm, get_vm


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
                     ("termination — Porteiro gera SSL via Certbot", "termination")],
                    value="passthrough", id="f-modo",
                )
                yield Label("HTTP (porta 80):")
                yield Select(
                    [("on  — encaminhar HTTP", "on"), ("off — bloquear HTTP", "off")],
                    value="on", id="f-http-on",
                )
                yield Label("HTTPS (porta 443):")
                yield Select(
                    [("on  — encaminhar HTTPS", "on"), ("off — bloquear HTTPS", "off")],
                    value="on", id="f-https-on",
                )
                with Horizontal(classes="modal-footer"):
                    yield Button("← Voltar",  id="btn-back",   variant="default")
                    yield Button("Testar",     id="btn-test",   variant="primary")
                    yield Button("Finalizar",  id="btn-save",   variant="success")

    def on_mount(self) -> None:
        self._show_step(1)

    def _show_step(self, step: int) -> None:
        self.query_one("#step-1").display = (step == 1)
        self.query_one("#step-2").display = (step == 2)
        label = "Etapa 1 de 2 — Identificação" if step == 1 else "Etapa 2 de 2 — Configuração de Rede"
        self.query_one("#wizard-step-label", Static).update(f"[dim]{label}[/]")
        self._step = step

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
            # Check for duplicate names/IPs
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
            ip      = self.query_one("#f-ip",      Input).value.strip()
            http_on = self.query_one("#f-http-on", Select).value
            port    = "80" if http_on == "on" else "443"
            if ip:
                self.test_connectivity(ip, port)

        elif bid == "btn-save":
            nome     = self.query_one("#f-nome",     Input).value.strip()
            desc     = self.query_one("#f-desc",     Input).value.strip()
            ip       = self.query_one("#f-ip",       Input).value.strip()
            modo     = self.query_one("#f-modo",     Select).value
            http_on  = self.query_one("#f-http-on",  Select).value
            https_on = self.query_one("#f-https-on", Select).value
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
            self.app.notify(f"✅ Sucesso! Ping OK e porta {p} aberta em {ip}.", severity="information")
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
                 ("termination — Porteiro gera SSL via Certbot", "termination")],
                value=vm.modo, id="f-modo",
            )
            yield Label("HTTP (porta 80):")
            yield Select(
                [("on  — encaminhar HTTP", "on"), ("off — bloquear HTTP", "off")],
                value=vm.http_on, id="f-http-on",
            )
            yield Label("HTTPS (porta 443):")
            yield Select(
                [("on  — encaminhar HTTPS", "on"), ("off — bloquear HTTPS", "off")],
                value=vm.https_on, id="f-https-on",
            )
            yield Label("Descrição:")
            yield Input(placeholder="ex: Docker Apps", id="f-desc", value=vm.descricao)
            with Horizontal(classes="modal-footer"):
                yield Button("Testar",   variant="primary", id="btn-test")
                yield Button("Salvar",   variant="success", id="btn-save")
                yield Button("Cancelar", id="btn-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel":
            self.dismiss(None)
            return
        if event.button.id == "btn-test":
            ip = self.query_one("#f-ip", Input).value.strip()
            http_on = self.query_one("#f-http-on", Select).value
            port = "80" if http_on == "on" else "443"
            if ip:
                self.test_connectivity(ip, port)
            return
        vm = self._vm
        ip       = self.query_one("#f-ip",       Input).value.strip()
        modo     = self.query_one("#f-modo",     Select).value
        http_on  = self.query_one("#f-http-on",  Select).value
        https_on = self.query_one("#f-https-on", Select).value
        desc     = self.query_one("#f-desc",     Input).value.strip()
        if not ip:
            self.query_one("#f-ip", Input).focus()
            return
        # Check for duplicate IPs (excluding current VM)
        all_vms = load_vms()
        if any(v.ip == ip and v.nome != vm.nome for v in all_vms):
            other = next(v.nome for v in all_vms if v.ip == ip)
            self.app.notify(f"O IP {ip} já está em uso pela VM '{other}'.", severity="error")
            self.query_one("#f-ip", Input).focus()
            return
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
            self.app.notify(f"✅ Sucesso! Ping OK e porta {p} aberta em {ip}.", severity="information")
        except Exception:
            self.app.notify(f"⚠ Ping OK em {ip}, mas a porta {port} parece fechada.", severity="warning")




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


# ── Tela principal de VMs ─────────────────────────────────────────────────────

class VMsScreen(Vertical):

    def compose(self) -> ComposeResult:
        with Horizontal(classes="toolbar"):
            yield Button("＋ Nova VM",  id="btn-add",    classes="btn-add")
            yield Button("✎ Editar",    id="btn-edit",   classes="btn-edit")
            yield Button("✕ Excluir",   id="btn-delete", classes="btn-delete")
            yield Button("⇄ Portas",    id="btn-ports",  classes="btn-apply")
        yield DataTable(id="vms-table", cursor_type="row")
        yield Static("", id="vm-status-bar", classes="muted-text")

    def on_mount(self) -> None:
        t = self.query_one("#vms-table", DataTable)
        t.add_columns("Nome", "IP", "HTTP", "HTTPS", "Modo", "Desc", "Doms")
        self.refresh_table()

    def refresh_table(self) -> None:
        t = self.query_one("#vms-table", DataTable)
        t.clear()
        vms     = load_vms()
        domains = load_domains()
        for vm in vms:
            dom_count = sum(1 for d in domains if d.vm_nome == vm.nome)
            h = f"[green]{vm.porta_http}[/]"  if vm.http_on  == "on" else "[red]✕[/]"
            s = f"[green]{vm.porta_https}[/]" if vm.https_on == "on" else "[red]✕[/]"
            t.add_row(vm.nome, vm.ip, h, s, vm.modo, vm.descricao, str(dom_count),
                      key=vm.nome)
        bar = self.query_one("#vm-status-bar", Static)
        bar.update(f"  {len(vms)} VM(s) cadastrada(s)")

    def _selected_vm_name(self) -> str | None:
        t = self.query_one("#vms-table", DataTable)
        if t.row_count == 0:
            return None
        row = t.get_row_at(t.cursor_row)
        return str(row[0]) if row else None

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
                self.app.push_screen(PortsModal(nome), self._on_ports)
            else:
                self.app.notify("Selecione uma VM para gerenciar portas.", severity="warning")

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


# ── Modal: Ativar/Desativar portas ────────────────────────────────────────────

class PortsModal(ModalScreen[None]):
    def __init__(self, nome: str) -> None:
        super().__init__()
        self._nome = nome

    def compose(self) -> ComposeResult:
        vm = get_vm(self._nome)
        with Vertical(classes="modal-form"):
            yield Label(f"Portas — {self._nome} ({vm.ip if vm else ''})",
                        classes="modal-title")
            yield Label("HTTP:")
            yield Select(
                [("on — encaminhar HTTP", "on"), ("off — bloquear HTTP", "off")],
                value=vm.http_on if vm else "on", id="p-http",
            )
            yield Label("HTTPS:")
            yield Select(
                [("on — encaminhar HTTPS", "on"), ("off — bloquear HTTPS", "off")],
                value=vm.https_on if vm else "on", id="p-https",
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
            vm.http_on  = self.query_one("#p-http",  Select).value
            vm.https_on = self.query_one("#p-https", Select).value
            update_vm(vm)
        self.dismiss(None)
