import sqlite3


conn = sqlite3.connect('wresty.db')
cur = conn.cursor()

# cur.execute('''
# CREATE TABLE IF NOT EXISTS people (first_name TEXT, last_name TEXT)
# ''')

names_list = [
  ('roger'), ('match'),
  ('lelu'), ('ham')
]

cur.executemany('''
insert into people (first_name, last_name) values (?, ?)
''')
conn.commit()

cur.close()
conn.close()
