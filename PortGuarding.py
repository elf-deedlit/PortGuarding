#!/usr/bin/env python3
# vim:set ts=4 sw=4 et smartindent fileencoding=utf-8:
import datetime
import os
import sqlite3
import socket
from sqlite3.dbapi2 import Error
from threading import Thread
import time
import concurrent.futures
import queue
from config import *

DBFILE = os.path.join(os.path.abspath(os.path.dirname(__file__)), RECORD_FILENAME)
socket.setdefaulttimeout(CONNECT_TIMEOUT)

def create_database(conn: sqlite3.connect) -> None:
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

class ThreadVariable(object):
    quit = False
    msg_queue = None
    db_queue = None
    def __init__(self) -> None:
        super().__init__()
        self.msg_queue = queue.LifoQueue()
        self.db_queue = queue.LifoQueue()
    
    def __delattr__(self, name: str) -> None:
        if self.conn:
            self.conn.commit()
            self.conn.close()
            self.conn = None
        return super().__delattr__(name)

    def is_quit(self) -> bool:
        return self.quit
    
    def set_quit(self) -> None:
        self.quit = True

    def add_msg(self, msg: str) -> None:
        self.msg_queue.put(msg)

    def add_db(self, data: list) -> None:
        self.db_queue.put(data)

def msg_loop(gbl: ThreadVariable) -> None:
    '''msg表示用ループ'''
    while True:
        if gbl.msg_queue.empty():
            if gbl.is_quit():
                break
            time.sleep(1)
            continue
        print(gbl.msg_queue.get())
    # print('msg loop quit')

def db_loop(gbl: ThreadVariable) -> None:
    '''db登録用ループ'''
    SQL = 'INSERT INTO record (id, response, guarding, msg) VALUES (?, ?, ?, ?)'
    with sqlite3.connect(DBFILE) as conn:
        while True:
            if gbl.db_queue.empty():
                if gbl.is_quit():
                    break
                time.sleep(1)
                continue
            try:
                cur = conn.cursor()
                data = gbl.db_queue.get()
                cur.execute(SQL, data)
                cur.close()
                conn.commit()
            except sqlite3.Error as err:
                print(err)
    # print('db loop quit')

def main_loop(host: str, port: int, host_id: int, gbl: ThreadVariable) -> None:
    '''メインループ'''
    prev_status = 0
    while not gbl.is_quit():
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as skt:
            msg = None
            status = 0
            try:
                stime = time.time()
                skt.connect((host, port))
                laps = time.time() - stime
                skt.shutdown(socket.SHUT_RDWR)
                msg = u'Status OK'
                gbl.add_db((host_id, laps, 0, u''))
            except socket.timeout:
                # タイムアウトを記録
                msg = u'Connection Timeout'
                status = 1
            except socket.gaierror as err:
                # 名前解決エラー
                args = err.args
                msg = '{0}({1})'.format(args[1], args[0])
                status = 2
            except OSError as err:
                # 上記以外のエラー
                args = err.args
                msg = '{0}({1})'.format(args[1], args[0])
                status = 3

            if status != 0:
                gbl.add_db((host_id, 0.0, status, msg))

            if status != prev_status:
                ntime = datetime.datetime.now()
                gbl.add_msg('[{3:%Y/%m/%d %H:%M:%S}] {0}({1}): {2}'.format(host, port, msg, ntime))
                prev_status = status

            # 何秒待つか計算
            if status == 0:
                # 1分後
                sec = 600
            else:
                # エラーになったので1秒後に
                sec = 10
            while sec > 0 and (not gbl.is_quit()):
                time.sleep(0.1)
                sec -= 1
    # print('{0}({1}): guarding loop quit'.format(host, port))

def main():
    '''Main Function'''
    with concurrent.futures.ThreadPoolExecutor() as executor:
        gbl = ThreadVariable()
        futures = []
        futures.append(executor.submit(msg_loop, gbl))
        futures.append(executor.submit(db_loop, gbl))
        with sqlite3.connect(DBFILE) as conn:
            create_database(conn)
            cur = conn.cursor()
            for host, port in GUARD_LIST:
                host_id = get_hostid(cur, host, port)
                futures.append(executor.submit(main_loop, host, port, host_id, gbl))
            cur.close()
            conn.commit()
        while not gbl.is_quit():
            try:
                #print("wait:{0:%Y/%m/%d %H:%M:%S}".format(datetime.datetime.now()))
                time.sleep(1)
            except KeyboardInterrupt:
                # どうもプロセスを終了させる方法はないっぽい？
                # https://www.google.co.jp/search?q=threadpoolexecutor+python+%E7%B5%82%E4%BA%86%E3%81%95%E3%81%9B%E3%82%8B&newwindow=1&source=hp&ei=Yrb_YK2LKYq2oASZjYLQCw&iflsig=AINFCbYAAAAAYP_Ecie9tB9cY2-eJi1rn2gk0bsYBSeW&oq=threadpoolexecutor+python+%E7%B5%82%E4%BA%86%E3%81%95%E3%81%9B%E3%82%8B&gs_lcp=Cgdnd3Mtd2l6EAMyBQgAEM0CMgUIABDNAjIFCAAQzQI6CAgAELEDEIMBOgIIADoECAAQBDoECAAQEzoGCAAQHhATOggIABAIEB4QEzoICAAQBRAeEBM6BggAEAQQHjoECAAQHjoICAAQCBAEEB46BggAEAgQHjoFCCEQoAFQ_AtY5kdg6EpoAnAAeACAAZcCiAG1EpIBBzExLjEwLjGYAQCgAQKgAQGqAQdnd3Mtd2l6sAEA&sclient=gws-wiz&ved=0ahUKEwitxOzl3YLyAhUKG4gKHZmGALoQ4dUDCAo&uact=5
                # for future in futures:
                #     print(id(future), f"running: {future.running()}", f"cancelled: {future.cancelled()}")
                # これはうまくいかなかった。
                # https://qiita.com/Yukimura127/items/2380931ac5efcd635d05
                # for process in executor._processes.values():
                #     process.kill()

                gbl.set_quit()
    # print(u'exit')

if __name__ == '__main__':
    main()
