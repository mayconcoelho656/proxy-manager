"""Dashboard — visão geral do sistema."""
from __future__ import annotations
from textual.app import ComposeResult
from textual.widgets import Static, DataTable, Label
from textual.containers import Horizontal, Vertical, ScrollableContainer

from pm.data import load_vms, load_domains, read_log
from pm.nginx import nginx_status
from pm import certbot


class DashboardScreen(ScrollableContainer):
    DEFAULT_CSS = ""

    def compose(self) -> ComposeResult:
        with Horizontal(id="stats-row"):
            yield Static("", id="stat-vms",    classes="stat-box")
            yield Static("", id="stat-domains", classes="stat-box")
            yield Static("", id="stat-nginx",   classes="stat-box")
            yield Static("", id="stat-certs",   classes="stat-box")

        yield Label("  VMs cadastradas", classes="section-title")
        yield DataTable(id="dash-vms-table", cursor_type="row")

        yield Label("  Domínios vinculados", classes="section-title")
        yield DataTable(id="dash-domains-table", cursor_type="row")

        yield Label("  Log recente", classes="section-title")
        yield Static("", id="dash-log")

    def on_mount(self) -> None:
        self.refresh_data()

    def refresh_data(self) -> None:
        vms     = load_vms()
        domains = load_domains()
        status  = nginx_status()
        certs   = certbot.list_certs() if certbot.is_installed() else []

        # Stats
        nginx_color = "green" if status == "active" else "red"
        nginx_icon  = "✓ ativo" if status == "active" else "✗ parado"

        self.query_one("#stat-vms").update(
            f"[bold cyan]{len(vms)}[/]\n[dim]VMs[/]")
        self.query_one("#stat-domains").update(
            f"[bold cyan]{len(domains)}[/]\n[dim]Domínios[/]")
        self.query_one("#stat-nginx").update(
            f"[bold {nginx_color}]{nginx_icon}[/]\n[dim]NGINX[/]")
        self.query_one("#stat-certs").update(
            f"[bold cyan]{len(certs)}[/]\n[dim]Certificados SSL[/]")

        # VMs table
        t = self.query_one("#dash-vms-table", DataTable)
        t.clear(columns=True)
        t.add_columns("Nome", "IP", "HTTP", "HTTPS", "Modo", "Domínios")
        for vm in vms:
            dom_count = sum(1 for d in domains if d.vm_nome == vm.nome)
            http_s  = f"[green]{vm.porta_http}[/]"  if vm.http_on  == "on" else "[red]✕[/]"
            https_s = f"[green]{vm.porta_https}[/]" if vm.https_on == "on" else "[red]✕[/]"
            modo_s  = f"[cyan]{vm.modo}[/]"
            t.add_row(vm.nome, vm.ip, http_s, https_s, modo_s, str(dom_count))

        # Domains table
        t2 = self.query_one("#dash-domains-table", DataTable)
        t2.clear(columns=True)
        t2.add_columns("Domínio", "VM", "Tipo", "Backend", "Modo", "SSL")
        for d in domains:
            vm = next((v for v in vms if v.nome == d.vm_nome), None)
            modo   = vm.modo if vm else "?"
            ssl_s  = "[green]OK[/]" if d.has_cert else "[dim]sem cert[/]"
            bp     = d.backend_port or "-"
            t2.add_row(d.dominio, d.vm_nome, d.tipo, bp, modo, ssl_s)

        # Log
        log = read_log(20)
        self.query_one("#dash-log").update(f"[dim]{log}[/]")
