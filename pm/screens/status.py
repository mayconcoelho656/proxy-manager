"""Tela de Status e NGINX."""
from __future__ import annotations
from textual.app import ComposeResult
from textual.widgets import Button, Static, RichLog
from textual.containers import Horizontal, Vertical, ScrollableContainer
import threading

from pm.data import read_log, clear_log
from pm.nginx import generate_nginx, reload_nginx, test_nginx, nginx_status, \
    NGINX_HTTP_CONF, NGINX_STREAM_CONF, NGINX_TERMINATION_CONF


class StatusScreen(Vertical):

    def compose(self) -> ComposeResult:
        with Horizontal(classes="toolbar"):
            yield Button("⟳ Aplicar + Recarregar NGINX", id="btn-apply",  classes="btn-add")
            yield Button("✎ Testar config",               id="btn-test",   classes="btn-edit")
            yield Button("↺ Atualizar",                   id="btn-refresh",classes="btn-apply")
            yield Button("🗑 Limpar Log",                id="btn-clear-log", classes="btn-delete")

        with Horizontal():
            yield Static("", id="nginx-status-box", classes="stat-box")
            yield Static("", id="conf-files-box",   classes="stat-box")

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
