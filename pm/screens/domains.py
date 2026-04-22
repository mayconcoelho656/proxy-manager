"""Tela de domínios com vincular/editar/excluir."""
from __future__ import annotations
from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import DataTable, Button, Label, Input, Select, Static
from textual.containers import Horizontal, Vertical

from pm.data import (Domain, load_vms, load_domains, get_domain,
                     add_domain, update_domain, delete_domain)


# ── Modal: Vincular / Editar Domínio ─────────────────────────────────────────

class DomainFormModal(ModalScreen[Domain | None]):
    def __init__(self, domain: Domain | None = None) -> None:
        super().__init__()
        self._domain = domain

    def compose(self) -> ComposeResult:
        d    = self._domain
        vms  = load_vms()
        title = f"Editar: {d.dominio}" if d else "Vincular Domínio → VM"

        with Vertical(classes="modal-form"):
            yield Label(title, classes="modal-title")

            if not d:
                yield Label("Domínio:")
                yield Input(placeholder="ex: n8n.meusite.com", id="f-domain")

            yield Label("VM de destino:")
            vm_opts = [(f"{v.nome}  ({v.ip}) [{v.modo}]", v.nome) for v in vms]
            
            # Se o domínio existe mas a VM foi removida, adiciona opção temporária para evitar erro
            if d and d.vm_nome not in [v.nome for v in vms]:
                vm_opts.append((f"[red]Removida ({d.vm_nome})[/]", d.vm_nome))

            current_val = ""
            if d:
                current_val = d.vm_nome
            elif vms:
                current_val = vms[0].nome

            yield Select(vm_opts, value=current_val, id="f-vm")

            yield Label("Tipo de tráfego:")
            yield Select(
                [("ambos — HTTP + HTTPS", "ambos"),
                 ("http  — Apenas HTTP",   "http"),
                 ("https — Apenas HTTPS",  "https")],
                value=d.tipo if d else "ambos", id="f-tipo",
            )

            yield Label("Porta do app na VM (termination):")
            yield Input(placeholder="ex: 3000, 8080 (deixe vazio para passthrough)",
                        id="f-bport", value=d.backend_port if d else "")

            with Horizontal(classes="modal-footer"):
                yield Button("Salvar", variant="success", id="btn-save")
                yield Button("Cancelar", id="btn-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel":
            self.dismiss(None)
            return

        d       = self._domain
        dominio = d.dominio if d else self.query_one("#f-domain", Input).value.strip()
        dominio = dominio.replace("https://", "").replace("http://", "").split("/")[0]
        vm_nome = self.query_one("#f-vm",    Select).value
        tipo    = self.query_one("#f-tipo",  Select).value
        bport   = self.query_one("#f-bport", Input).value.strip()
        email   = d.email_ssl if d else ""

        if not dominio:
            self.app.notify("Preencha o domínio.", severity="warning")
            return
        if not vm_nome:
            self.app.notify("Selecione uma VM de destino.", severity="warning")
            return

        self.dismiss(Domain(dominio, vm_nome, tipo, bport, email))


# ── Modal: Confirmar exclusão ─────────────────────────────────────────────────

class ConfirmModal(ModalScreen[bool]):
    def __init__(self, msg: str) -> None:
        super().__init__()
        self._msg = msg

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-form"):
            yield Label("⚠  Confirmar", classes="modal-title")
            yield Static(self._msg)
            with Horizontal(classes="modal-footer"):
                yield Button("Confirmar", variant="error", id="btn-yes")
                yield Button("Cancelar", id="btn-no")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "btn-yes")


# ── Tela principal de Domínios ────────────────────────────────────────────────

class DomainsScreen(Vertical):

    def compose(self) -> ComposeResult:
        with Horizontal(classes="toolbar"):
            yield Button("＋ Vincular",   id="btn-add",    classes="btn-add")
            yield Button("✎ Editar",      id="btn-edit",   classes="btn-edit")
            yield Button("✕ Desvincular", id="btn-delete", classes="btn-delete")
        with Horizontal(classes="filter-bar"):
            yield Button("Ver Todos", id="btn-filter-all", classes="btn-filter -active-filter")
            yield Button("Termination", id="btn-filter-term", classes="btn-filter")
            yield Button("Passthrough", id="btn-filter-pass", classes="btn-filter")
        yield DataTable(id="domains-table", cursor_type="row")
        yield Static("", id="dom-status-bar", classes="muted-text")

    def on_mount(self) -> None:
        self._current_filter = "all"
        t = self.query_one("#domains-table", DataTable)
        t.add_columns("Domínio", "VM", "Tipo", "Backend", "Modo", "SSL")
        self.refresh_table()

    def refresh_table(self) -> None:
        t       = self.query_one("#domains-table", DataTable)
        t.clear()
        domains = load_domains()
        vms     = {v.nome: v for v in load_vms()}
        count   = 0
        for d in domains:
            vm   = vms.get(d.vm_nome)
            vm_display = d.vm_nome
            if not vm:
                vm_display = f"[red]Removido ({d.vm_nome})[/]"
                modo = "[red]?[/]"
            else:
                modo = vm.modo

            if hasattr(self, "_current_filter"):
                if self._current_filter == "termination" and modo != "termination": continue
                if self._current_filter == "passthrough" and modo != "passthrough": continue

            ssl  = "[green]OK[/]" if d.has_cert else ("[dim]sem cert[/]" if modo == "termination" else "[dim]n/a[/]")
            bp   = d.backend_port or "-"
            t.add_row(d.dominio, vm_display, d.tipo, bp, modo, ssl, key=d.dominio)
            count += 1
            
        filter_str = f" | Filtro: {self._current_filter.upper()}" if hasattr(self, "_current_filter") else ""
        self.query_one("#dom-status-bar", Static).update(f"  {count} domínio(s) listado(s){filter_str}")

    def _selected_domain(self) -> str | None:
        t = self.query_one("#domains-table", DataTable)
        if t.row_count == 0:
            return None
        row = t.get_row_at(t.cursor_row)
        return str(row[0]) if row else None

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-add":
            self.app.push_screen(DomainFormModal(), self._on_save)
        elif event.button.id == "btn-edit":
            name = self._selected_domain()
            if name:
                d = get_domain(name)
                if d:
                    self.app.push_screen(DomainFormModal(d), self._on_save)
            else:
                self.app.notify("Selecione um domínio para editar.", severity="warning")

        elif event.button.id == "btn-delete":
            name = self._selected_domain()
            if name:
                self.app.push_screen(
                    ConfirmModal(f"Desvincular o domínio '[bold]{name}[/]'?"),
                    lambda ok: self._on_delete(ok, name),
                )
            else:
                self.app.notify("Selecione um domínio para desvincular.", severity="warning")
        elif event.button.id in ("btn-filter-all", "btn-filter-term", "btn-filter-pass"):
            for btn in self.query(".btn-filter"):
                btn.remove_class("-active-filter")
            event.button.add_class("-active-filter")
            
            if event.button.id == "btn-filter-all":
                self._current_filter = "all"
            elif event.button.id == "btn-filter-term":
                self._current_filter = "termination"
            elif event.button.id == "btn-filter-pass":
                self._current_filter = "passthrough"
            self.refresh_table()

    def _on_save(self, d: Domain | None) -> None:
        if d:
            if get_domain(d.dominio):
                update_domain(d)
            else:
                add_domain(d)
            self.refresh_table()

    def _on_delete(self, ok: bool, name: str) -> None:
        if ok:
            delete_domain(name)
            self.refresh_table()
