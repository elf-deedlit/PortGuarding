#!/usr/bin/env python3
# vim:set ts=4 sw=4 et smartindent fileencoding=utf-8:

# 設定ファイル
GUARD_LIST = (
#   ('HOST or IP', 'PORT'),
    ('denchu.jp', 443),
    ('denchu.jp', 22),      # Connection Timeout
)

RECORD_FILENAME = 'port_guarding.sqlite'

CONNECT_TIMEOUT = 3.0

LEFT_DAYS = 30
