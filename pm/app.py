"""Aplicação principal Textual — Proxy Manager."""
from __future__ import annotations
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Header, Footer, Tabs, Tab, ContentSwitcher, Button, Static, Label
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen

from pm.screens.dashboard import DashboardScreen
from pm.screens.vms       import VMsScreen
from pm.screens.domains   import DomainsScreen
from pm.screens.ssl       import SSLScreen
from pm.screens.status    import StatusScreen
from pm.screens.tutorial  import TutorialScreen


class HelpModal(ModalScreen[None]):
    def compose(self) -> ComposeResult:
        with Vertical(id="help-modal", classes="modal-form"):
            yield Label("Atalhos do Sistema", classes="modal-title")
            keys = [
                ("1 a 6", "Alterna entre as abas principais"),
                ("↑↓←→", "Navega nas tabelas e rola o conteúdo"),
                ("Tab", "Avança para o próximo campo ou botão"),
                ("Shift+Tab", "Volta para o campo ou botão anterior"),
                ("Enter", "Confirma os formulários e opções"),
                ("Esc", "Fecha janelas e menus (Modais)"),
                ("r", "Atualiza os dados da aba atual"),
                ("q", "Encerra o Proxy Manager"),
                ("?", "Mostra esta tela de ajuda"),
            ]
            for key, desc in keys:
                yield Static(f"[bold cyan]{key:<8}[/] {desc}", classes="help-line")
            with Horizontal(classes="modal-footer"):
                yield Button("Fechar", variant="primary", id="btn-close-help")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-close-help":
            self.dismiss(None)


class ProxyManagerApp(App):
    """Proxy Manager — Porteiro NGINX."""

    ENABLE_COMMAND_PALETTE = False

    CSS_PATH = "app.tcss"
    TITLE    = "Proxy Manager — Porteiro NGINX"
    SUB_TITLE = "Gerenciador de proxy reverso e SSL"

    BINDINGS = [
        Binding("1", "switch_tab('dashboard')", "Dashboard", show=True),
        Binding("2", "switch_tab('vms')",       "VMs",       show=True),
        Binding("3", "switch_tab('domains')",   "Domínios",  show=True),
        Binding("4", "switch_tab('ssl')",       "SSL",       show=True),
        Binding("5", "switch_tab('status')",   "Status",   show=True),
        Binding("6", "switch_tab('tutorial')",  "Tutorial", show=True),
        Binding("r", "refresh",                 "Atualizar", show=True),
        Binding("q", "quit",                    "Sair",      show=True),
        Binding("question_mark", "help",        "Ajuda",     show=True),
    ]

    def compose(self) -> ComposeResult:
        yield Header(icon="")
        with Horizontal(id="top-bar"):
            yield Tabs(
                Tab("📊 Dashboard", id="dashboard"),
                Tab("🖥  VMs", id="vms"),
                Tab("🌐 Domínios", id="domains"),
                Tab("🔒 SSL/Certbot", id="ssl"),
                Tab("📋 Status", id="status"),
                Tab("📖 Tutorial", id="tutorial"),
                id="tabs"
            )
            yield Button("⟳ Atualizar", id="btn-top-refresh", classes="btn-top")
            yield Button("✕ Sair", id="btn-top-quit", classes="btn-top btn-top-quit")

        with ContentSwitcher(initial="screen-dashboard", id="content-switcher"):
            yield DashboardScreen(id="screen-dashboard")
            yield VMsScreen(id="screen-vms")
            yield DomainsScreen(id="screen-domains")
            yield SSLScreen(id="screen-ssl")
            yield StatusScreen(id="screen-status")
            yield TutorialScreen(id="screen-tutorial")
        yield Footer()

    def on_tabs_tab_activated(self, event: Tabs.TabActivated) -> None:
        if event.tab and event.tab.id:
            self.query_one("#content-switcher", ContentSwitcher).current = f"screen-{event.tab.id}"
            self.action_refresh()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-top-refresh":
            self.action_refresh()
        elif event.button.id == "btn-top-quit":
            self.exit()

    def action_switch_tab(self, tab_id: str) -> None:
        self.query_one("#tabs", Tabs).active = tab_id
        self.query_one("#content-switcher", ContentSwitcher).current = f"screen-{tab_id}"
        self.action_refresh()

    def action_help(self) -> None:
        self.push_screen(HelpModal())

    def action_refresh(self) -> None:
        """Atualiza a aba ativa."""
        active = self.query_one("#content-switcher", ContentSwitcher).current
        if active:
            try:
                widget = self.query_one(f"#{active}")
                if hasattr(widget, "refresh_table"):
                    widget.refresh_table()
                elif hasattr(widget, "refresh_data"):
                    widget.refresh_data()
                elif hasattr(widget, "refresh_all"):
                    widget.refresh_all()
            except Exception:
                pass


def main() -> None:
    app = ProxyManagerApp()
    app.run()


if __name__ == "__main__":
    main()
