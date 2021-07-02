#!/usr/bin/env python3
# vim:set ts=4 sw=4 et smartindent fileencoding=utf-8:
import datetime
import os
import sqlite3
import socket
import time
from config import *

DBFILE = os.path.join(os.path.abspath(os.path.dirname(__file__)), RECORD_FILENAME)
socket.setdefaulttimeout(CONNECT_TIMEOUT)

def create_database(conn):
    '''データベース テーブル作成'''
    cur = conn.cursor()
    sql = '''CREATE TABLE IF NOT EXISTS hosts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        port INTEGER
    )'''
    cur.execute(sql)

    sql = '''CREATE TABLE IF NOT EXISTS record (
        id INTEGER,
        response FLOAT,
        guarding INTEGER,
        msg TEXT,
        dtime DATETIME DEFAULT (datetime('now', 'localtime'))
    )
    '''
    cur.execute(sql)

    conn.commit()

def get_hostid(cur, name, port):
    '''ホスト名とポートを記録'''
    sql = 'SELECT id FROM hosts WHERE name=? AND port=?'
    cur.execute(sql, (name, port))
    rslt = cur.fetchone()
    if rslt:
        return rslt[0]
    else:
        sql = 'INSERT INTO hosts (name, port) VALUES (?, ?)'
        cur.execute(sql, (name, port))
        return cur.lastrowid

def main_loop(conn):
    '''メインループ'''
    SQL = 'INSERT INTO record (id, response, guarding, msg) VALUES (?, ?, ?, ?)'
    while True:
        cur = conn.cursor()
        for host, port in GUARD_LIST:
            host_id = get_hostid(cur, host, port)
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as skt:
                try:
                    stime = time.time()
                    skt.connect((host, port))
                    laps = time.time() - stime
                    cur.execute(SQL, (host_id, laps, 0, u''))
                    skt.shutdown(socket.SHUT_RDWR)
                except socket.timeout:
                    # タイムアウトを記録
                    cur.execute(SQL, (host_id, 0.0, 1, u'Connection Timeout'))
                except socket.gaierror as err:
                    # 名前解決エラー
                    args = err.args
                    msg = '{0}({1})'.format(args[1], args[0])
                    cur.execute(SQL, (host_id, 0.0, 1, msg))
                except OSError as err:
                    # 上記以外のエラー
                    args = err.args
                    msg = '{0}({1})'.format(args[1], args[0])
                    cur.execute(SQL, (host_id, 0.0, 1, msg))
        conn.commit()
        # 何秒待つか計算
        nowtime = datetime.datetime.now()
        nxttime = nowtime + datetime.timedelta(minutes=1)
        waittime = nxttime.replace(second=0, microsecond=0) - nowtime
        time.sleep(waittime.total_seconds())

def main():
    '''Main Function'''
    with sqlite3.connect(DBFILE) as conn:
        create_database(conn)
        try:
            main_loop(conn)
        except KeyboardInterrupt:
            pass
        conn.commit()

if __name__ == '__main__':
    main()

