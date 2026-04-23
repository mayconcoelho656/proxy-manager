#!/bin/bash
# ============================================================
#  PROXY MANAGER — Instalador
#  Suporte: Debian 11/12/13 · Ubuntu 22.04/24.04
# ============================================================

set -e

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$SCRIPT_DIR/.venv"
INSTALL_BIN="/usr/local/bin/proxy-manager"
NGINX_CONF="/etc/nginx/nginx.conf"
STREAM_DIR="/etc/nginx/stream.conf.d"

_log()  { echo -e "${CYAN}[install]${NC} $1"; }
_ok()   { echo -e "${GREEN}[  ok  ]${NC} $1"; }
_warn() { echo -e "${YELLOW}[ warn ]${NC} $1"; }
_err()  { echo -e "${RED}[ erro ]${NC} $1"; exit 1; }
_sep()  { echo -e "${CYAN}────────────────────────────────────────────────${NC}"; }

# ── Root check ───────────────────────────────────────────────
[[ $EUID -ne 0 ]] && _err "Execute como root: sudo bash install.sh"

echo ""
echo -e "${CYAN}${BOLD}╔══════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}${BOLD}║   Proxy Manager — Porteiro NGINX             ║${NC}"
echo -e "${CYAN}${BOLD}║   Instalador v1.1                            ║${NC}"
echo -e "${CYAN}${BOLD}╚══════════════════════════════════════════════╝${NC}"
echo ""

# ── 1. Dependências de sistema ────────────────────────────────
_sep
_log "Verificando dependencias de sistema..."

APT_PKGS=()
command -v nginx    &>/dev/null || APT_PKGS+=(nginx)
command -v certbot  &>/dev/null || APT_PKGS+=(certbot)
command -v git      &>/dev/null || APT_PKGS+=(git)
command -v python3  &>/dev/null || APT_PKGS+=(python3)
command -v openssl  &>/dev/null || APT_PKGS+=(openssl)
dpkg -l python3-venv &>/dev/null 2>&1 || APT_PKGS+=(python3-venv)
dpkg -l python3-pip  &>/dev/null 2>&1 || APT_PKGS+=(python3-pip)

if [[ ${#APT_PKGS[@]} -gt 0 ]]; then
    _warn "Pacotes faltando: ${APT_PKGS[*]}"
    read -rp "  Instalar agora via apt? [s/N] " ans
    [[ "$ans" =~ ^[sS]$ ]] || _err "Instale manualmente os pacotes necessarios."
    apt-get update -qq
    apt-get install -y "${APT_PKGS[@]}"
fi
_ok "nginx, certbot, git, python3, openssl: OK"

# ── 2. Módulo Stream do NGINX ────────────────────────────────────
_sep
_log "Instalando modulo stream do NGINX (libnginx-mod-stream)..."
# Sempre instala/verifica o pacote para garantir o arquivo em modules-enabled/
if apt-get install -y libnginx-mod-stream &>/dev/null; then
    _ok "libnginx-mod-stream instalado/atualizado"
else
    _warn "Nao foi possivel instalar libnginx-mod-stream."
    _warn "Instale manualmente: apt install libnginx-mod-stream"
    read -rp "  Continuar mesmo assim? [s/N] " ans
    [[ "$ans" =~ ^[sS]$ ]] || exit 1
fi
# Verificacao final
if ls /etc/nginx/modules-enabled/*stream* &>/dev/null || nginx -V 2>&1 | grep -q "with-stream"; then
    _ok "Modulo NGINX stream confirmado"
else
    _warn "Modulo stream pode nao estar ativo — verifique /etc/nginx/modules-enabled/"
fi

# ── 3. Diretórios e arquivos de dados ────────────────────────
_sep
_log "Criando estrutura de dados..."
mkdir -p /etc/proxy-manager/backups
mkdir -p /etc/proxy-manager/certs
mkdir -p "$STREAM_DIR"
mkdir -p /var/www/certbot
touch /etc/proxy-manager/vms.conf
touch /etc/proxy-manager/domains.conf
touch /var/log/proxy-manager.log
chmod 640 /var/log/proxy-manager.log
_ok "/etc/proxy-manager/  (dados e backups)"
_ok "/etc/proxy-manager/certs/  (certificados importados)"
_ok "$STREAM_DIR  (configs NGINX stream)"
_ok "/var/www/certbot  (webroot ACME)"
_ok "/var/log/proxy-manager.log"

# ── 4. Desativar site default do NGINX ────────────────────────────────────
_sep
_log "Desativando site 'default' do NGINX (interfere com o Porteiro)..."
if [[ -L "/etc/nginx/sites-enabled/default" ]]; then
    rm -f /etc/nginx/sites-enabled/default
    _ok "Site default removido de sites-enabled/"
else
    _ok "Site default ja estava inativo"
fi

# ── 5. Configurar nginx.conf para bloco stream ────────────────────────────
_sep
_log "Configurando nginx.conf para bloco stream..."
if grep -q "stream.conf.d" "$NGINX_CONF" 2>/dev/null; then
    _ok "Include stream ja existe em nginx.conf"
else
    cp "$NGINX_CONF" "${NGINX_CONF}.bak-proxy-manager"
    _ok "Backup: ${NGINX_CONF}.bak-proxy-manager"

    # Adiciona o include NO FINAL do arquivo (fora do bloco http{})
    # Isso é necessário pois o bloco stream{} deve estar no nível raiz do nginx.conf
    printf '\n# Proxy Manager — stream routing (porta 443, SNI)\ninclude %s/*.conf;\n' \
        "$STREAM_DIR" >> "$NGINX_CONF"

    if nginx -t 2>/dev/null; then
        _ok "nginx.conf atualizado e validado (stream no nivel raiz)"
    else
        _warn "nginx.conf com erros — restaurando backup..."
        cp "${NGINX_CONF}.bak-proxy-manager" "$NGINX_CONF"
        _warn "Adicione manualmente ao FINAL do nginx.conf (fora do http{}):"
        _warn "  include ${STREAM_DIR}/*.conf;"
    fi
fi

# ── 6. Python venv e dependências ────────────────────────────────────
_sep
_log "Configurando ambiente Python (venv)..."
if [[ ! -f "$VENV/bin/python3" ]]; then
    python3 -m venv "$VENV"
    _ok "venv criado em $VENV"
else
    _ok "venv ja existe em $VENV"
fi

_log "Instalando dependencias Python (textual, rich)..."
"$VENV/bin/pip" install --upgrade pip --quiet
"$VENV/bin/pip" install -r "$SCRIPT_DIR/requirements.txt" --quiet
_ok "Dependencias Python instaladas"

# ── 7. Wrapper executável em /usr/local/bin ────────────────────────────
_sep
_log "Criando comando global 'proxy-manager'..."

cat > "$INSTALL_BIN" <<EOF
#!/bin/bash
# Proxy Manager — Porteiro NGINX
# Gerado por install.sh
exec "$VENV/bin/python3" "$SCRIPT_DIR/proxy-manager.py" "\$@"
EOF

chmod +x "$INSTALL_BIN"
_ok "Comando instalado: $INSTALL_BIN"

# ── 8. Permissões do proxy-manager.py ──────────────────────────────────
chmod +x "$SCRIPT_DIR/proxy-manager.py"

# ── 9. Testar NGINX ─────────────────────────────────────────────────────
_sep
_log "Testando configuracao do NGINX..."
if nginx -t 2>/dev/null; then
    systemctl reload nginx 2>/dev/null || true
    _ok "NGINX recarregado com sucesso"
else
    _warn "NGINX reportou erros — verifique com: nginx -t"
fi

# ── Resumo final ──────────────────────────────────────────────
echo ""
echo -e "${GREEN}${BOLD}╔══════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}${BOLD}║   Instalacao concluida com sucesso!          ║${NC}"
echo -e "${GREEN}${BOLD}╚══════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${BOLD}Como usar:${NC}"
echo -e "    ${YELLOW}sudo proxy-manager${NC}"
echo ""
echo -e "  ${BOLD}Dados:${NC}         /etc/proxy-manager/"
echo -e "  ${BOLD}VMs:${NC}           /etc/proxy-manager/vms.conf"
echo -e "  ${BOLD}Dominios:${NC}      /etc/proxy-manager/domains.conf"
echo -e "  ${BOLD}Certs manual:${NC}  /etc/proxy-manager/certs/"
echo -e "  ${BOLD}Backups:${NC}       /etc/proxy-manager/backups/"
echo -e "  ${BOLD}Log:${NC}           /var/log/proxy-manager.log"
echo -e "  ${BOLD}NGINX stream:${NC}  $STREAM_DIR/"
echo ""
echo -e "  ${CYAN}Modos de VM suportados:${NC}"
echo -e "    ${BOLD}passthrough${NC}  — encaminha HTTPS/HTTP direto para a VM (proxy interno na VM)"
echo -e "    ${BOLD}termination${NC}  — Porteiro termina SSL via Certbot e faz proxy HTTP para a VM"
echo ""
echo -e "  ${CYAN}Dica:${NC} Sempre execute como root (sudo) pois o painel"
echo -e "        gerencia NGINX, certificados e configuracoes de sistema."
echo ""
