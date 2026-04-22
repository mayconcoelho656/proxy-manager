# Proxy Manager — Porteiro NGINX 🚪

**Gerenciador de proxy reverso e SSL via terminal (TUI) para Linux**  
Baseado em [Textual](https://github.com/Textualize/textual) · Python 3 · NGINX

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Platform](https://img.shields.io/badge/platform-Linux-blue.svg)](https://www.linux.org/)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Language](https://img.shields.io/badge/idioma-PT--BR%20only-green.svg)]()

---

## O que é?

O **Proxy Manager Porteiro** é um painel de controle TUI (interface de texto interativa) que roda direto no terminal Linux para gerenciar:

- **VMs e servidores internos** (IP, modo de operação)
- **Domínios vinculados** e roteamento de tráfego HTTP/HTTPS
- **Certificados SSL** via Let's Encrypt (Certbot) ou importação manual (Cloudflare, etc.)
- **NGINX** como proxy reverso com geração automática de configurações
- **Renovação automática** de certificados via crontab

---

## 🎯 Para quem é essa solução?

### O problema real: 1 IP público, múltiplas máquinas

Se você já tentou hospedar múltiplos projetos, aplicações ou websites em casa ou num servidor próprio, provavelmente bateu nessa parede:

> *Seu roteador (gateway) permite apenas **um único encaminhamento de porta (port forwarding)** — ou seja, as portas `80` (HTTP) e `443` (HTTPS) só podem ser mapeadas para **um único dispositivo** na sua rede interna.*

Isso significa que toda a sua infraestrutura — VMs, containers Docker, aplicações Node.js, PHP, projetos pessoais, homelabs — fica **presa atrás de uma única máquina**, incapaz de expor serviços individuais com domínio e HTTPS para o mundo.

```
Internet (1 IP público)
        │
        │  port forwarding :80 e :443
        ▼
┌───────────────────────┐
│   Apenas 1 máquina    │ ← único destino possível no roteador
│   recebe tudo         │
└───────────────────────┘
        ✗ bloqueadas
   VM Docker    CloudPanel    Node.js App
   apps/api     websites      projeto pessoal
  (sem acesso) (sem acesso)  (sem acesso)
```

Muitos desenvolvedores e entusiastas chegam a **descontinuar seus projetos**, se sentem forçados a contratar um VPS pago e abrir mão da independência da própria infraestrutura — frustrados por algo que parece tão simples mas que poucos solucionam de forma prática.

> Essa funcionalidade é uma das **mais pedidas pela comunidade** há anos em fóruns, redes sociais e até nos próprios sistemas de feedback de fabricantes consolidados como a Ubiquiti (UniFi) — e que ainda **não foi implementada de forma nativa** por nenhum deles.

---

### A solução: um único Porteiro para toda a sua rede

O **Proxy Manager Porteiro** foi criado exatamente para resolver esse problema.

Ele roda em **uma única máquina** (servidor, VM ou até um mini PC) que recebe todo o tráfego da internet pelas portas `80` e `443`, e redistribui inteligentemente para **qualquer número de máquinas, VMs ou containers** na sua rede interna — com suporte a múltiplos domínios, SSL automático e controle total via painel TUI.

```
Internet (1 IP público)
        │
        ▼
┌───────────────────────────────┐
│     Porteiro NGINX (esta VM)  │  ← porta 80 e 443
│   proxy reverso + SSL + SNI   │
└──────┬──────────┬─────────────┘
       │          │          │
       ▼          ▼          ▼
  VM Docker   CloudPanel   Servidor Node.js
  apps/api    websites     projeto pessoal
```

---

### Para quem serve

| Perfil | Uso |
|---|---|
| 🏠 **Homelab iniciante** | Quer expor 1 ou 2 projetos com HTTPS gratuito (Let's Encrypt) sem complicação |
| 🛠️ **Desenvolvedor independente** | Hospeda múltiplas aplicações (Docker, Node, PHP) em diferentes VMs com domínios próprios |
| 🖥️ **Usuário avançado** | Opera múltiplos servidores, VMs e containers especializados, cada um com seu proxy interno (Traefik, Caddy) e certificados próprios (Cloudflare, 15 anos) |
| 🏢 **Infra doméstica/corporativa** | Centraliza o roteamento de tráfego de toda a rede interna em um único ponto de entrada |

**Em todos os casos:** sem precisar de múltiplos IPs públicos, sem reconfigurar o roteador, sem migrar para VPS — apenas um Porteiro na frente da sua rede fazendo o trabalho.



## Requisitos

| Componente | Mínimo |
|---|---|
| Sistema Operacional | Debian 11/12 ou Ubuntu 22.04/24.04 |
| Python | 3.10+ |
| NGINX | Qualquer versão recente com módulo `stream` |
| Certbot | Para emissão de certificados Let's Encrypt |
| OpenSSL | Para leitura de validade de certificados |
| Git | Para clonar o repositório |
| Permissão | `root` (sudo) |
| Idioma | Português (PT-BR) — English not available |

> 🇧🇷 **Este gerenciador é inteiramente em Português (PT-BR).** Não há suporte para outros idiomas no momento.

---

## Instalação

```bash
# 1. Clonar o repositório
git clone https://github.com/mayconcoelho656/proxy-manager.git
cd proxy-manager

# 2. Executar o instalador (requer root)
sudo ./install.sh
```

> **Por que `./`?** O `sudo` não inclui o diretório atual no PATH por segurança.
> O `./` indica explicitamente "execute este arquivo aqui nesta pasta".

O instalador irá automaticamente:
- Verificar e instalar `nginx`, `certbot`, `git`, `python3`, `openssl`
- Instalar o módulo `libnginx-mod-stream` para roteamento HTTPS via SNI
- Criar os diretórios de dados em `/etc/proxy-manager/`
- Configurar o `nginx.conf` para incluir o bloco `stream`
- Criar o ambiente virtual Python (`.venv`) com as dependências
- Registrar o comando global `/usr/local/bin/proxy-manager`

---

## Uso

Após a instalação, basta executar:

```bash
sudo proxy-manager
```

> **Nota:** O `sudo` é obrigatório pois o painel gerencia configurações do NGINX, certificados SSL em `/etc/` e regras do crontab — operações que requerem privilégios de root.

---

## Navegação no painel

| Tecla | Ação |
|---|---|
| `1` a `6` | Alterna entre as abas (Dashboard, VMs, Domínios, SSL, Status, Tutorial) |
| `↑` `↓` `←` `→` | Navega nas tabelas e rola o conteúdo |
| `Tab` | Avança para o próximo campo ou botão |
| `Shift+Tab` | Volta para o campo ou botão anterior |
| `Enter` | Confirma formulários e opções |
| `Esc` | Fecha janelas/modais |
| `r` | Atualiza os dados da aba atual |
| `q` | Encerra o Proxy Manager |
| `?` | Exibe os atalhos de teclado |

---

## Modos de Operação

### 🔀 Passthrough
O Porteiro repassa o tráfego diretamente para a VM sem inspecionar o SSL.  
**Ideal para:** VMs com proxy reverso próprio (Traefik, Caddy, Nginx interno).

```
Internet → Porteiro (porta 80/443) → VM (proxy interno) → Aplicação
                                          ↑ SSL gerenciado aqui
```

### 🔒 Termination
O Porteiro encerra a conexão SSL e encaminha HTTP internamente para a aplicação.  
**Ideal para:** Aplicações diretas (Node.js, Python, PHP) sem proxy próprio.

```
Internet → Porteiro (porta 443, SSL aqui) → Aplicação (porta interna ex: 3000)
     ↓
  HTTP 80 → redirecionado 301 → HTTPS automaticamente
```

---

## Certificados SSL

### Let's Encrypt (gratuito)
1. Vá na aba **SSL/Certbot**
2. Selecione o domínio vinculado a uma VM em modo **Termination**
3. Clique em **＋ Let's Encrypt**, informe seu e-mail e confirme
4. Ative o **⏰ Cron** para renovação automática (a cada 90 dias)

### Importação Manual (Cloudflare Origin, etc.)
1. Vá na aba **SSL/Certbot**
2. Selecione o domínio e clique em **＋ Importar**
3. Cole o conteúdo do certificado público e da chave privada
4. O Porteiro salva em `/etc/proxy-manager/certs/<domínio>/` e recarrega o NGINX

> Certificados importados são identificados na tabela como **Importado** com a data de expiração lida automaticamente via `openssl`.

---

## Estrutura de arquivos

```
proxy-manager/
├── install.sh              # Instalador
├── proxy-manager.py        # Entry point
├── requirements.txt        # Dependências Python
└── pm/
    ├── app.py              # App principal (Textual)
    ├── app.tcss            # Estilos TUI
    ├── data.py             # Modelos e persistência
    ├── nginx.py            # Geração de configs NGINX
    ├── certbot.py          # Integração Certbot
    └── screens/
        ├── dashboard.py    # Aba Dashboard
        ├── vms.py          # Aba VMs
        ├── domains.py      # Aba Domínios
        ├── ssl.py          # Aba SSL/Certbot
        ├── status.py       # Aba Status/Log
        └── tutorial.py     # Aba Tutorial
```

### Dados persistidos em `/etc/proxy-manager/`

| Arquivo/Dir | Conteúdo |
|---|---|
| `vms.conf` | VMs cadastradas (pipe-separated) |
| `domains.conf` | Domínios vinculados |
| `backups/` | Backups automáticos das configs NGINX |
| `certs/<domínio>/` | Certificados importados manualmente |

---

## Configurações NGINX geradas

O Porteiro gera e mantém automaticamente 3 arquivos:

| Arquivo | Função |
|---|---|
| `/etc/nginx/conf.d/porteiro-http.conf` | Bloco HTTP (porta 80), redirects e proxy |
| `/etc/nginx/conf.d/porteiro-termination.conf` | Bloco HTTPS com SSL termination |
| `/etc/nginx/stream.conf.d/porteiro-stream.conf` | Bloco stream para SNI passthrough |

> ⚠️ Não edite esses arquivos manualmente — eles são regenerados pelo painel.

---

## Fluxo rápido — primeira configuração

```
1. sudo proxy-manager
2. Aba VMs       → ＋ Nova VM (nome, IP, modo)
3. Aba Domínios  → ＋ Vincular (domínio, VM, porta backend)
4. Aba SSL       → ＋ Let's Encrypt ou ＋ Importar
5. Aba Status    → ⟳ Aplicar + Recarregar NGINX
6. Aba SSL       → ⏰ Cron (ativar renovação automática)
```

---

## Licença

MIT © 2025 — Livre para uso, modificação e distribuição.
