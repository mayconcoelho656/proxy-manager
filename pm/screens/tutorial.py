"""Tela de Tutorial / Guia de uso com fluxogramas visuais."""
from __future__ import annotations
from textual.app import ComposeResult
from textual.widgets import Static
from textual.containers import Vertical, ScrollableContainer


TUTORIAL_CONTENT = """\
[bold white on #1a1a2e]  📖 Guia de Uso — Proxy Manager Porteiro  [/]


[bold cyan]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/]
[bold yellow]  🖥  MODO PASSTHROUGH — Fluxo de tráfego[/]
[bold cyan]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/]

  O Porteiro repassa o tráfego sem inspecionar o SSL.
  Ideal para VMs que já têm proxy próprio (Traefik, Caddy, Nginx).

[bold green]  Fluxo HTTP + HTTPS (recomendado):[/]

  ┌──────────────┐  :80/:443   ┌─────────────────┐  :80/:443   ┌──────────────────┐
  │   Internet   │ ──────────► │    Porteiro     │ ──────────► │  VM (Traefik /   │
  │              │             │  (Passthrough)  │             │   Caddy / Nginx) │
  └──────────────┘             └─────────────────┘             └──────────────────┘
                                                                        │
                                                                        │ SSL aqui
                                                                        ▼
                                                               ┌──────────────────┐
                                                               │   Aplicação      │
                                                               │  (porta interna) │
                                                               └──────────────────┘

  [dim]• HTTP ON  → proxy interno recebe o desafio Let's Encrypt (ACME)[/]
  [dim]• HTTPS ON → proxy interno gerencia SSL e redireciona HTTP → HTTPS[/]

[bold yellow]  Fluxo com Certificado Importado (ex: Cloudflare 15 anos):[/]

  ┌──────────────┐   :443      ┌─────────────────┐   :443     ┌──────────────────┐
  │   Internet   │ ──────────► │    Porteiro     │ ──────────►│   VM (proxy      │
  │  (só HTTPS)  │             │  (Passthrough)  │            │   com cert       │
  └──────────────┘             └─────────────────┘            │   importado)     │
                                [red]  HTTP bloqueado  [/]            └──────────────────┘

  [dim]• HTTP OFF → nenhuma conexão não-segura chega à VM[/]


[bold cyan]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/]
[bold magenta]  🔒 MODO TERMINATION — Fluxo de tráfego[/]
[bold cyan]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/]

  O Porteiro termina o SSL aqui e encaminha HTTP interno para a aplicação.
  Ideal para apps diretos (Node.js, Python, PHP) sem proxy próprio na VM.

[bold green]  Fluxo com Let's Encrypt (recomendado):[/]

  ┌──────────────┐   :443      ┌──────────────────────────┐   :3000    ┌──────────┐
  │   Internet   │ ──────────► │  Porteiro (Termination)  │ ─────────► │   App    │
  │  (só HTTPS)  │             │  ✅ SSL encerrado aqui   │   HTTP     │  na VM   │
  └──────────────┘             │  📜 Cert Let's Encrypt   │   interno  └──────────┘
          │                    └──────────────────────────┘
          │ :80
          ▼
  ┌──────────────┐
  │   Porteiro   │ ──► redireciona 301 → HTTPS automaticamente
  │  HTTP → 301  │
  └──────────────┘
    [red]HTTP bloqueado[/] na VM (porta 80 interna não usada)

[bold yellow]  Fluxo com Certificado Importado (ex: Cloudflare Origin):[/]

  ┌──────────────┐   :443      ┌──────────────────────────┐   :8080    ┌──────────┐
  │   Internet   │ ──────────► │  Porteiro (Termination)  │ ─────────► │   App    │
  │  (só HTTPS)  │             │  ✅ SSL encerrado aqui   │   HTTP     │  na VM   │
  └──────────────┘             │  📜 Cert Importado       │   interno  └──────────┘
                               └──────────────────────────┘
  [dim]• Certificado colado manualmente na aba SSL/Certbot → Importar[/]
  [dim]• Porteiro usa o cert automaticamente no NGINX gerado[/]


[bold cyan]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/]
[bold green]  ⚡ FLUXO RÁPIDO — Configuração completa (Termination + LE)[/]
[bold cyan]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/]

  ┌─────────────────────────────────────────────────────────────────────┐
  │  1. Aba VMs → ＋ Nova VM                                            │
  │     • Modo: termination | HTTP: OFF | HTTPS: ON                     │
  │     • Porta do app na etapa 2 via "Portas" (ex: 3000)               │
  └───────────────────────────────┬─────────────────────────────────────┘
                                  │
                                  ▼
  ┌─────────────────────────────────────────────────────────────────────┐
  │  2. Aba Domínios → ＋ Vincular                                      │
  │     • Selecione a VM e tipo: https                                  │
  │     • Informe a porta backend (ex: 3000)                            │
  └───────────────────────────────┬─────────────────────────────────────┘
                                  │
                                  ▼
  ┌─────────────────────────────────────────────────────────────────────┐
  │  3. Aba SSL/Certbot → selecione o domínio → ＋ Let's Encrypt        │
  │     • Informe o e-mail e confirme                                   │
  │     • Aguarde a emissão (requer DNS apontando para este servidor)   │
  └───────────────────────────────┬─────────────────────────────────────┘
                                  │
                                  ▼
  ┌─────────────────────────────────────────────────────────────────────┐
  │  4. Aba Status → ⟳ Aplicar + Recarregar NGINX                       │
  │     • Verifique se NGINX está RODANDO (verde)                       │
  └───────────────────────────────┬─────────────────────────────────────┘
                                  │
                                  ▼
  ┌─────────────────────────────────────────────────────────────────────┐
  │  5. Aba SSL/Certbot → ⏰ Cron → ativar                              │
  │     • Renovação automática diária às 03:00h                         │
  └───────────────────────────────┬─────────────────────────────────────┘
                                  │
                                  ▼
         [bold green]✅  Site acessível em https://seudominio.com[/]


[bold cyan]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/]
[bold blue]  🔄 RENOVAÇÃO AUTOMÁTICA — Decisão[/]
[bold cyan]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/]

                         ┌──────────────────┐
                         │  Tipo de Cert?   │
                         └────────┬─────────┘
                    ┌─────────────┴─────────────┐
                    ▼                           ▼
          ┌──────────────────┐       ┌──────────────────┐
          │  Let's Encrypt   │       │    Importado     │
          │  (90 dias)       │       │ (Cloudflare etc) │
          └────────┬─────────┘       └────────┬─────────┘
                   │                          │
                   ▼                          ▼
        ┌──────────────────┐       ┌──────────────────┐
        │  Ative o Cron!   │       │  Cron não afeta  │
        │  ⏰ Cron: ON     │       │  Coluna Auto: -  │
        │  renovação auto  │       │  Gerenciar       │
        └──────────────────┘       │  manualmente     │
                                   └──────────────────┘
"""


class TutorialScreen(Vertical):

    def compose(self) -> ComposeResult:
        with ScrollableContainer():
            yield Static(TUTORIAL_CONTENT, id="tutorial-content", markup=True)
