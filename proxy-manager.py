#!/usr/bin/env python3
"""Entry point — Proxy Manager."""
import os
import sys

def main():
    if os.geteuid() != 0:
        print("\033[31mErro: execute como root:\033[0m sudo python3 proxy-manager.py")
        sys.exit(1)

    # Garante diretórios necessários
    import pathlib
    for d in ["/etc/proxy-manager/backups", "/etc/nginx/stream.conf.d", "/var/www/certbot"]:
        pathlib.Path(d).mkdir(parents=True, exist_ok=True)
    for f in ["/etc/proxy-manager/vms.conf", "/etc/proxy-manager/domains.conf",
              "/var/log/proxy-manager.log"]:
        pathlib.Path(f).touch(exist_ok=True)

    from pm.app import main as run_app
    run_app()

if __name__ == "__main__":
    main()
