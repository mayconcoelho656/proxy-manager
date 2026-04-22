"""Geração das configurações NGINX."""
from __future__ import annotations
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from pm.data import load_vms, load_domains, get_vm, BACKUP_DIR, log_action

NGINX_HTTP_CONF        = Path("/etc/nginx/conf.d/porteiro-http.conf")
NGINX_TERMINATION_CONF = Path("/etc/nginx/conf.d/porteiro-termination.conf")
NGINX_STREAM_CONF      = Path("/etc/nginx/stream.conf.d/porteiro-stream.conf")
TERMINATION_PORT       = 4430


def backup_configs() -> None:
    ts   = datetime.now().strftime("%Y%m%d-%H%M%S")
    bdir = BACKUP_DIR / ts
    bdir.mkdir(parents=True, exist_ok=True)
    for f in [NGINX_HTTP_CONF, NGINX_TERMINATION_CONF, NGINX_STREAM_CONF]:
        if f.exists():
            shutil.copy(f, bdir / f.name)


def _header() -> list[str]:
    return ["# Gerado pelo proxy-manager (Python)", "# NAO edite manualmente", ""]


def _gen_http() -> str:
    lines = _header()
    for d in load_domains():
        if d.tipo == "https":
            continue
        vm = get_vm(d.vm_nome)
        if not vm or vm.http_on == "off":
            continue
        lines += [f"server {{", f"    listen 80;", f"    server_name {d.dominio};", ""]
        if vm.modo == "termination":
            lines += ["    location /.well-known/acme-challenge/ {",
                      "        root /var/www/certbot;", "    }"]
            cert, _ = d.cert_path
            if cert:
                lines += ["    location / {",
                          "        return 301 https://$host$request_uri;", "    }"]
            else:
                bp = d.backend_port or "80"
                lines += ["    location / {",
                          f"        proxy_pass http://{vm.ip}:{bp};",
                          "        proxy_set_header Host $host;",
                          "        proxy_set_header X-Real-IP $remote_addr;", "    }"]
        else:
            lines += ["    location / {",
                      f"        proxy_pass http://{vm.ip}:{vm.porta_http};",
                      "        proxy_set_header Host $host;",
                      "        proxy_set_header X-Real-IP $remote_addr;",
                      "        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;",
                      "    }"]
        lines += ["}", ""]
    return "\n".join(lines)


def _gen_stream() -> str:
    lines = _header() + ["stream {", "    map $ssl_preread_server_name $backend_https {"]
    for d in load_domains():
        if d.tipo == "http":
            continue
        vm = get_vm(d.vm_nome)
        if not vm or vm.https_on == "off":
            continue
        if vm.modo == "passthrough":
            lines.append(f"        {d.dominio}    {vm.ip}:{vm.porta_https};")
        else:
            lines.append(f"        {d.dominio}    127.0.0.1:{TERMINATION_PORT};")
    lines += ["    }", "", "    server {", "        listen 443;",
              "        ssl_preread on;", "        proxy_pass $backend_https;",
              "    }", "}"]
    return "\n".join(lines)


def _gen_termination() -> str:
    lines = _header()
    for d in load_domains():
        if d.tipo == "http":
            continue
        vm = get_vm(d.vm_nome)
        if not vm or vm.https_on == "off" or vm.modo != "termination":
            continue
        cert, key = d.cert_path
        if not cert or not key:
            lines += [f"# AVISO: sem certificado para {d.dominio}", ""]
            continue
        bp = d.backend_port or "80"
        lines += [
            f"server {{",
            f"    listen {TERMINATION_PORT} ssl;",
            f"    server_name {d.dominio};",
            "",
            f"    ssl_certificate     {cert};",
            f"    ssl_certificate_key {key};",
            "    ssl_protocols TLSv1.2 TLSv1.3;",
            "    ssl_ciphers HIGH:!aNULL:!MD5;",
            "",
            "    location / {",
            f"        proxy_pass http://{vm.ip}:{bp};",
            "        proxy_set_header Host $host;",
            "        proxy_set_header X-Real-IP $remote_addr;",
            "        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;",
            "        proxy_set_header X-Forwarded-Proto https;",
            "    }",
            "}",
            "",
        ]
    return "\n".join(lines)


def generate_nginx() -> None:
    backup_configs()
    NGINX_HTTP_CONF.parent.mkdir(parents=True, exist_ok=True)
    NGINX_STREAM_CONF.parent.mkdir(parents=True, exist_ok=True)
    NGINX_HTTP_CONF.write_text(_gen_http())
    NGINX_STREAM_CONF.write_text(_gen_stream())
    NGINX_TERMINATION_CONF.write_text(_gen_termination())
    log_action("Configuração NGINX gerada")


def test_nginx() -> tuple[bool, str]:
    r = subprocess.run(["nginx", "-t"], capture_output=True, text=True)
    return r.returncode == 0, r.stderr


def reload_nginx() -> tuple[bool, str]:
    ok, err = test_nginx()
    if not ok:
        return False, err
    r = subprocess.run(["systemctl", "reload", "nginx"], capture_output=True, text=True)
    if r.returncode == 0:
        log_action("NGINX recarregado com sucesso")
    return r.returncode == 0, r.stderr


def nginx_status() -> str:
    r = subprocess.run(["systemctl", "is-active", "nginx"], capture_output=True, text=True)
    return r.stdout.strip()
