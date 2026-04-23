"""Tela de Status e NGINX."""
from __future__ import annotations
from textual.app import ComposeResult
from textual.widgets import Button, Static, RichLog
from textual.containers import Horizontal, Vertical, ScrollableContainer
import threading
import socket
import subprocess

from pm.data import read_log, clear_log
from pm.nginx import generate_nginx, reload_nginx, test_nginx, nginx_status, \
    NGINX_HTTP_CONF, NGINX_STREAM_CONF, NGINX_TERMINATION_CONF


def _check_port_listening(port: int) -> bool:
    """Verifica se o NGINX local está ouvindo na porta especificada."""
    import subprocess
    r = subprocess.run(
        ["ss", "-tlnp", f"sport = :{port}"],
        capture_output=True, text=True
    )
    return str(port) in r.stdout


def _check_port_public(host: str, port: int, timeout: float = 4.0) -> tuple[bool, str]:
    """
    Tenta conectar na porta do próprio IP público para verificar
    se o Porteiro está acessível da internet.
    """
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True, "acessível"
    except socket.timeout:
        return False, "timeout (firewall bloqueando?)"
    except ConnectionRefusedError:
        return False, "conexão recusada (porta fechada)"
    except OSError as e:
        return False, str(e)


def _get_public_ip() -> str:
    """Obtém o IP público do servidor consultando um serviço externo."""
    try:
        r = subprocess.run(
            ["curl", "-s", "--max-time", "5", "https://ifconfig.me"],
            capture_output=True, text=True
        )
        ip = r.stdout.strip()
        if ip and len(ip) < 46:  # IPv4 ou IPv6 válido
            return ip
    except Exception:
        pass
    return ""


class StatusScreen(Vertical):

    def compose(self) -> ComposeResult:
        with Horizontal(classes="toolbar"):
            yield Button("⟳ Aplicar + Recarregar NGINX", id="btn-apply",      classes="btn-add")
            yield Button("✎ Testar config",               id="btn-test",       classes="btn-edit")
            yield Button("🌐 Testar Portas 80/443",       id="btn-test-ports", classes="btn-apply")
            yield Button("↺ Atualizar",                   id="btn-refresh",    classes="btn-apply")
            yield Button("🗑 Limpar Log",                 id="btn-clear-log",  classes="btn-delete")

        with Horizontal():
            yield Static("", id="nginx-status-box", classes="stat-box")
            yield Static("", id="conf-files-box",   classes="stat-box")
            yield Static("", id="ports-status-box", classes="stat-box")

        yield Static("[bold cyan]  Configuração NGINX gerada[/]", classes="section-title")
        yield RichLog(id="conf-log", highlight=True, markup=True, wrap=False)

        yield Static("[bold cyan]  Log do Proxy Manager[/]", classes="section-title")
        yield RichLog(id="pm-log", highlight=True, markup=True, wrap=True)

    def on_mount(self) -> None:
        self.refresh_all()

    def refresh_all(self) -> None:
        self._refresh_status()
        self._refresh_conf()
        self._refresh_log()

    def _refresh_status(self) -> None:
        status = nginx_status()
        color  = "green" if status == "active" else "red"
        icon   = "✓ RODANDO" if status == "active" else "✗ PARADO"
        self.query_one("#nginx-status-box", Static).update(
            f"NGINX\n[bold {color}]{icon}[/]")

        files = []
        for f in [NGINX_HTTP_CONF, NGINX_STREAM_CONF, NGINX_TERMINATION_CONF]:
            icon = "[green]✓[/]" if f.exists() else "[red]✗[/]"
            files.append(f"{icon} {f.name}")
        self.query_one("#conf-files-box", Static).update(
            "Arquivos .conf\n" + "\n".join(files))

    def _refresh_conf(self) -> None:
        log = self.query_one("#conf-log", RichLog)
        log.clear()
        for f in [NGINX_HTTP_CONF, NGINX_STREAM_CONF, NGINX_TERMINATION_CONF]:
            log.write(f"[bold cyan]=== {f} ===[/]")
            try:
                log.write(f.read_text() if f.exists() else "(arquivo não existe)")
            except Exception as e:
                log.write(f"[red]Erro: {e}[/]")
            log.write("")

    def _refresh_log(self) -> None:
        log = self.query_one("#pm-log", RichLog)
        log.clear()
        log.write(read_log(60))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-apply":
            threading.Thread(target=self._thread_apply, daemon=True).start()
        elif event.button.id == "btn-test":
            ok, err = test_nginx()
            info = "[green]✓ Configuração válida![/]" if ok else f"[red]✗ Erros:\n{err}[/]"
            self.query_one("#nginx-status-box", Static).update(info)
        elif event.button.id == "btn-test-ports":
            self.query_one("#ports-status-box", Static).update(
                "[yellow]⏳ Testando portas...[/]")
            threading.Thread(target=self._thread_test_ports, daemon=True).start()
        elif event.button.id == "btn-refresh":
            self.refresh_all()
        elif event.button.id == "btn-clear-log":
            clear_log()
            self._refresh_log()

    def _thread_apply(self) -> None:
        self.app.call_from_thread(
            self.query_one("#nginx-status-box", Static).update,
            "[yellow]Gerando configuração...[/]")
        generate_nginx()
        ok, err = reload_nginx()
        msg = "[green]✓ NGINX recarregado com sucesso![/]" if ok \
              else f"[red]✗ Erro ao recarregar:\n{err}[/]"
        self.app.call_from_thread(
            self.query_one("#nginx-status-box", Static).update, msg)
        self.app.call_from_thread(self.refresh_all)

    def _thread_test_ports(self) -> None:
        lines = ["[bold]Portas locais (ss):[/]"]

        # ── Teste local: ss -tlnp ─────────────────────────────────────────────
        for port in (80, 443):
            ok = _check_port_listening(port)
            icon = "[green]✓[/]" if ok else "[red]✗[/]"
            label = "NGINX ouvindo" if ok else "não encontrado"
            lines.append(f"  {icon} Porta {port}: {label}")

        # ── Teste público: tenta conectar via IP público ───────────────────────
        lines.append("")
        lines.append("[bold]Acesso externo (IP público):[/]")
        public_ip = _get_public_ip()
        if not public_ip:
            lines.append("  [yellow]⚠ Não foi possível obter o IP público[/]")
        else:
            lines.append(f"  [dim]IP público: {public_ip}[/]")
            for port in (80, 443):
                ok, msg = _check_port_public(public_ip, port)
                icon = "[green]✓[/]" if ok else "[red]✗[/]"
                lines.append(f"  {icon} Porta {port}: {msg}")

        result = "\n".join(lines)
        self.app.call_from_thread(
            self.query_one("#ports-status-box", Static).update,
            result
        )
