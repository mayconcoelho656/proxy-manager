"""Tela SSL / Certbot."""
from __future__ import annotations
import threading
from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import DataTable, Button, Label, Input, Static, TextArea, Checkbox
from textual.containers import Horizontal, Vertical

from pm.data import load_domains, load_vms, get_domain, update_domain
from pm import certbot as cb
from pm.nginx import generate_nginx, reload_nginx


class SSLScreen(Vertical):

    def compose(self) -> ComposeResult:
        with Horizontal(classes="toolbar"):
            yield Button("＋ Let's Encrypt", id="btn-issue",  classes="btn-add")
            yield Button("＋ Importar",       id="btn-import", classes="btn-add")
            yield Button("↺ Renovar",         id="btn-renew",  classes="btn-edit")
            yield Button("✕ Revogar",         id="btn-revoke", classes="btn-delete")
            yield Button("⏰ Cron",          id="btn-cron",   classes="btn-apply")
        yield DataTable(id="ssl-table", cursor_type="row")
        yield Static("", id="ssl-info", classes="info-panel")

    def on_mount(self) -> None:
        t = self.query_one("#ssl-table", DataTable)
        t.add_columns("Domínio", "VM", "Porta", "Status", "Tipo SSL", "Expiração", "Auto")
        self.refresh_table()

    def refresh_table(self) -> None:
        t       = self.query_one("#ssl-table", DataTable)
        t.clear()
        vms     = {v.nome: v for v in load_vms()}
        domains = [d for d in load_domains()
                   if (vm := vms.get(d.vm_nome)) and vm.modo == "termination"]
        for d in domains:
            ssl = "[green]✓ ativo[/]" if d.has_cert else "[red]✗ sem cert[/]"
            tipo, exp = d.cert_info
            if tipo == "Let's Encrypt":
                auto = "[green]ON[/]" if getattr(d, "auto_renew", "on") == "on" else "[red]OFF[/]"
            else:
                auto = "-"
            t.add_row(d.dominio, d.vm_nome, d.backend_port or "-", ssl, tipo, exp, auto,
                      key=d.dominio)
        info = self.query_one("#ssl-info", Static)
        cron_btn = self.query_one("#btn-cron", Button)
        if cb.has_cron():
            cron_btn.label = "⏰ Cron: ON"
            cron_btn.set_class(True, "btn-apply")
        else:
            cron_btn.label = "⏰ Cron: OFF"
            cron_btn.set_class(False, "btn-apply")
        
        if not cb.is_installed():
            info.update("[yellow]⚠ certbot não instalado. Execute: apt install certbot[/]")
        else:
            certs = cb.list_certs()
            info.update(f"[dim]{len(certs)} certificado(s) ativo(s)[/]")

    def _selected_domain(self) -> str | None:
        t = self.query_one("#ssl-table", DataTable)
        if t.row_count == 0:
            return None
        row = t.get_row_at(t.cursor_row)
        return str(row[0]) if row else None

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "btn-issue":
            name = self._selected_domain()
            if not name:
                return
            d = get_domain(name)
            if d:
                self.app.push_screen(EmailModal(name), self._do_issue)
        elif bid == "btn-import":
            name = self._selected_domain()
            if name:
                # Usa lambda para ignorar o resultado e forçar refresh_table
                self.app.push_screen(ManualCertModal(name), lambda r: self.refresh_table())
        elif bid == "btn-renew":
            name = self._selected_domain()
            if name:
                threading.Thread(target=self._thread_renew, args=(name,), daemon=True).start()
        elif bid == "btn-revoke":
            name = self._selected_domain()
            if name:
                self.app.push_screen(ConfirmRevokeModal(name), self._do_revoke)
        elif bid == "btn-cron":
            active = cb.toggle_cron()
            msg = "[green]Cron ATIVADO (diariamente às 03:00)[/]" if active else "[yellow]Cron DESATIVADO[/]"
            self.query_one("#ssl-info", Static).update(msg)
            self.refresh_table()

    def _do_revoke(self, result: bool) -> None:
        if result:
            name = self._selected_domain()
            if name:
                threading.Thread(target=self._thread_revoke, args=(name,), daemon=True).start()

    def _do_issue(self, result: tuple[str, str, str] | None) -> None:
        if result:
            name, email, auto = result
            threading.Thread(target=self._thread_issue, args=(name, email), daemon=True).start()

    def _set_info(self, msg: str) -> None:
        self.app.call_from_thread(self.query_one("#ssl-info", Static).update, msg)

    def _thread_issue(self, domain: str, email: str) -> None:
        self._set_info(f"[yellow]Emitindo certificado para {domain}...[/]")
        generate_nginx(); reload_nginx()
        ok, out = cb.issue_cert(domain, email)
        if ok:
            generate_nginx(); reload_nginx()
            self._set_info(f"[green]✓ Certificado emitido para {domain}![/]")
        else:
            self._set_info(f"[red]✗ Erro:\n{out[-400:]}[/]")
        self.app.call_from_thread(self.refresh_table)

    def _thread_renew(self, domain: str) -> None:
        self._set_info(f"[yellow]Renovando {domain}...[/]")
        ok, out = cb.renew_cert(domain)
        self._set_info(f"[green]✓ Renovado: {domain}[/]" if ok else f"[red]✗ {out[-300:]}[/]")
        self.app.call_from_thread(self.refresh_table)

    def _thread_revoke(self, domain: str) -> None:
        self._set_info(f"[yellow]Revogando {domain}...[/]")
        d = get_domain(domain)
        if not d:
            self._set_info(f"[red]✗ Domínio não encontrado.[/]")
            return
            
        tipo, _ = d.cert_info
        if tipo == "Let's Encrypt":
            ok, out = cb.delete_cert(domain)
        else:
            import shutil
            from pathlib import Path
            p = Path(f"/etc/proxy-manager/certs/{domain}")
            if p.exists():
                shutil.rmtree(p)
            ok, out = True, "Removido manualmente."

        if ok:
            generate_nginx(); reload_nginx()
            self._set_info(f"[green]✓ Certificado removido: {domain}[/]")
        else:
            self._set_info(f"[red]✗ Erro: {out}[/]")
        self.app.call_from_thread(self.refresh_table)


class EmailModal(ModalScreen[tuple[str, str, str] | None]):
    def __init__(self, domain: str) -> None:
        super().__init__()
        self._domain = domain

    def compose(self) -> ComposeResult:
        d = get_domain(self._domain)
        email_val = d.email_ssl if d else ""
        auto_val = (getattr(d, "auto_renew", "on") == "on") if d else True
        with Vertical(classes="modal-form", id="email-form"):
            yield Label(f"Emitir SSL — {self._domain}", classes="modal-title")
            yield Label("E-mail para Let's Encrypt:")
            yield Input(placeholder="admin@meusite.com", id="f-email", value=email_val)
            yield Checkbox("Renovar automaticamente?", value=auto_val, id="f-auto")
            with Horizontal(classes="modal-footer"):
                yield Button("Emitir", variant="success", id="btn-ok")
                yield Button("Cancelar", id="btn-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel":
            self.dismiss(None)
        elif event.button.id == "btn-ok":
            email = self.query_one("#f-email", Input).value.strip()
            auto = "on" if self.query_one("#f-auto", Checkbox).value else "off"
            if email:
                d = get_domain(self._domain)
                if d:
                    d.email_ssl = email
                    d.auto_renew = auto
                    update_domain(d)
                self.dismiss((self._domain, email, auto))


class ManualCertModal(ModalScreen[None]):
    def __init__(self, domain: str) -> None:
        super().__init__()
        self._domain = domain

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-form", id="manual-cert-form"):
            yield Label(f"Importar Certificado Manual — {self._domain}", classes="modal-title")
            yield Label("Certificado Público (fullchain.pem / .crt):")
            yield TextArea(id="f-cert", language="markdown")
            yield Label("Chave Privada (privkey.pem / .key):")
            yield TextArea(id="f-key", language="markdown")
            with Horizontal(classes="modal-footer"):
                yield Button("Salvar e Aplicar", variant="success", id="btn-save")
                yield Button("Cancelar", id="btn-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel":
            self.dismiss(None)
        elif event.button.id == "btn-save":
            cert = self.query_one("#f-cert", TextArea).text.strip()
            key = self.query_one("#f-key", TextArea).text.strip()
            if cert and key:
                from pathlib import Path
                cert_dir = Path(f"/etc/proxy-manager/certs/{self._domain}")
                cert_dir.mkdir(parents=True, exist_ok=True)
                (cert_dir / "fullchain.pem").write_text(cert + "\n")
                (cert_dir / "privkey.pem").write_text(key + "\n")
                
                # Regerar NGINX
                generate_nginx()
                reload_nginx()
                self.dismiss(None)

class ConfirmRevokeModal(ModalScreen[bool]):
    def __init__(self, domain: str) -> None:
        super().__init__()
        self._domain = domain

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-form"):
            yield Label(f"Revogar Certificado — {self._domain}", classes="modal-title")
            yield Label(f"Tem certeza que deseja excluir o certificado SSL?\n\nEle será removido permanentemente do servidor.", id="revoke-msg")
            with Horizontal(classes="modal-footer"):
                yield Button("Sim, Excluir", variant="error", id="btn-confirm")
                yield Button("Cancelar", id="btn-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-confirm":
            self.dismiss(True)
        else:
            self.dismiss(False)
