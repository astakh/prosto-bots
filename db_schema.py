import asyncpg
import app.config as config
import asyncio

async def get_schema(output_file="db_schema.txt"):
    conn = await asyncpg.connect(**config.DB_CONFIG)
    result = await conn.fetch("""
        SELECT 
            t.table_name AS "Таблица",
            c.column_name AS "Столбец",
            c.data_type AS "Тип данных",
            CASE 
                WHEN c.is_nullable = 'NO' THEN 'NOT NULL'
                ELSE 'NULL'
            END AS "Nullable",
            c.column_default AS "Значение по умолчанию",
            CASE 
                WHEN tc.constraint_type = 'PRIMARY KEY' THEN 'PRIMARY KEY'
                WHEN tc.constraint_type = 'FOREIGN KEY' THEN 'FOREIGN KEY -> ' || (
                    SELECT t_ref.table_name || '.' || ccu.column_name
                    FROM information_schema.constraint_column_usage ccu
                    JOIN information_schema.tables t_ref 
                        ON ccu.table_name = t_ref.table_name 
                        AND ccu.table_schema = t_ref.table_schema
                    WHERE ccu.constraint_name = tc.constraint_name
                    LIMIT 1
                )
                WHEN tc.constraint_type = 'UNIQUE' THEN 'UNIQUE'
                ELSE ''
            END AS "Ограничения"
        FROM 
            information_schema.tables t
        JOIN 
            information_schema.columns c 
            ON t.table_name = c.table_name 
            AND t.table_schema = c.table_schema
        LEFT JOIN 
            information_schema.key_column_usage kcu 
            ON c.table_name = kcu.table_name 
            AND c.column_name = kcu.column_name 
            AND c.table_schema = kcu.table_schema
        LEFT JOIN 
            information_schema.table_constraints tc 
            ON kcu.constraint_name = tc.constraint_name 
            AND kcu.table_name = tc.table_name 
            AND kcu.table_schema = tc.table_schema
        WHERE 
            t.table_schema = 'public'
        ORDER BY 
            t.table_name, c.ordinal_position;
    """)

    # Определяем фиксированные ширины колонок
    col_widths = {
        "Таблица": 20,
        "Столбец": 20,
        "Тип данных": 15,
        "Nullable": 10,
        "Значение по умолчанию": 30,
        "Ограничения": 40
    }

    # Заголовок
    header = (
        f"{'Таблица':<{col_widths['Таблица']}}|"
        f"{'Столбец':<{col_widths['Столбец']}}|"
        f"{'Тип данных':<{col_widths['Тип данных']}}|"
        f"{'Nullable':<{col_widths['Nullable']}}|"
        f"{'Значение по умолчанию':<{col_widths['Значение по умолчанию']}}|"
        f"{'Ограничения':<{col_widths['Ограничения']}}"
    )

    # Разделитель
    separator = "-" * (sum(col_widths.values()) + len(col_widths) - 1)

    # Открываем файл для записи
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(header + "\n")
        f.write(separator + "\n")

        # Записываем строки
        for row in result:
            table = (row['Таблица'] or '')[:col_widths['Таблица']].ljust(col_widths['Таблица'])
            column = (row['Столбец'] or '')[:col_widths['Столбец']].ljust(col_widths['Столбец'])
            data_type = (row['Тип данных'] or '')[:col_widths['Тип данных']].ljust(col_widths['Тип данных'])
            nullable = (row['Nullable'] or '')[:col_widths['Nullable']].ljust(col_widths['Nullable'])
            default = (str(row['Значение по умолчанию']) if row['Значение по умолчанию'] is not None else '')[:col_widths['Значение по умолчанию']].ljust(col_widths['Значение по умолчанию'])
            constraints = (row['Ограничения'] if row['Ограничения'] is not None else '')[:col_widths['Ограничения']].ljust(col_widths['Ограничения'])

            line = f"{table}|{column}|{data_type}|{nullable}|{default}|{constraints}"
            f.write(line + "\n")

    await conn.close()
    print(f"Структура базы данных записана в файл: {output_file}")

if __name__ == "__main__":
    asyncio.run(get_schema())