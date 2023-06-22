import sqlite3

BASE = 'selfstorage.db'


def SQL_register_new_user(tg_id, name):
    conn = sqlite3.connect(BASE)
    cur = conn.cursor()
    exec_text = f"""
        INSERT INTO 'users' (tg_id, name)
        VALUES ('{tg_id}', '{name}')
        """
    cur.execute(exec_text)
    conn.commit()
    conn.close()


def SQL_add_new_order(tg_id,
                      start_date,
                      duration=None,
                      weight=None,
                      capacity=None,
                      cost=None,
                      delivery=None,
                      delivery_time=None,
                      address=None,
                      phone=None):

    end_date = calculate_end_date(start_date, duration)

    conn = sqlite3.connect(BASE)
    cur = conn.cursor()
    exec_text = f"""
        INSERT INTO 'orders' (user_id, start_date, end_date, weight, capacity, cost, delivery, delivery_time, address, phone)
        VALUES ('{tg_id}','{start_date}','{end_date}','{weight}','{capacity}','{cost}','{delivery}','{delivery_time}','{address}','{phone}')
        """
    cur.execute(exec_text)
    conn.commit()
    conn.close()


def SQL_get_user_data(tg_id) -> dict:

    conn = sqlite3.connect(BASE)
    cur = conn.cursor()
    exec_text = f"SELECT * FROM 'users' WHERE tg_id is '{tg_id}'"
    cur.execute(exec_text)
    result = cur.fetchone()
    conn.close()

    if isinstance(result, type(None)):
        return False

    formated_result = {
        'tg_id': result[0],
        'name': result[1],
        'phone': result[2]
        }
    return formated_result


def SQL_put_user_phone(tg_id, phone):
    conn = sqlite3.connect(BASE)
    cur = conn.cursor()
    exec_text = f"UPDATE 'users' SET phone={phone} WHERE tg_id={tg_id}"
    cur.execute(exec_text)
    conn.commit()
    conn.close()


def calculate_end_date(start, duration):
    start_sep = start.split('.')
    start_sep[1] = str(int(start_sep[1]) + int(duration))
    if int(start_sep[1]) > 12:
        start_sep[1] = str(int(start_sep[1]) - 12)
        start_sep[2] = str(int(start_sep[2]) + 1)
    end_date = ".".join(start_sep)
    return end_date
