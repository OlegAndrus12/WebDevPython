# Як оголосити колонку

Три способи, усі робочі. Новий код — тільки перший.

```python
# 1. Сучасний (2.0): анотація + mapped_column
class User(Base):                      # class Base(DeclarativeBase)
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    bio: Mapped[str | None]
```

```python
# 2. Старий (1.x): Column, досі підтримується
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(120), nullable=False)
    bio = Column(String(200))          # nullable за замовчуванням
```

```python
# 3. Imperative: Table окремо, клас окремо (потрібно рідко — legacy-схеми)
reg = registry()
users = Table("users", reg.metadata,
              Column("id", Integer, primary_key=True),
              Column("name", String(120), nullable=False))
reg.map_imperatively(User, users)
```

Стилі 1 і 2 дають **однаковий** SQL:

```sql
CREATE TABLE users (
    id INTEGER NOT NULL,
    name VARCHAR(120) NOT NULL,
    bio VARCHAR(200),
    PRIMARY KEY (id)
)
```

Різниця не в SQL, а в тому, що знає Python: у старому стилі `nullable=False` —
аргумент, який легко забути, і mypy вважає `user.bio` за `str`. У новому
nullability **і є** анотацією, і mypy бачить, що `user.bio` може бути `None`.

## Старий стиль → новий

| замість | пиши |
| --- | --- |
| `declarative_base()` | `class Base(DeclarativeBase): pass` |
| `Column(Integer, primary_key=True)` | `Mapped[int] = mapped_column(primary_key=True)` |
| `Column(String(120), nullable=False)` | `Mapped[str] = mapped_column(String(120))` |
| `Column(String(120))` | `Mapped[str \| None] = mapped_column(String(120))` |
| `Column(Integer, default=0)` | `Mapped[int] = mapped_column(default=0)` |
| `Column(Integer, ForeignKey("users.id"))` | `Mapped[int] = mapped_column(ForeignKey("users.id"))` |
| `relationship("Video", backref="author")` | `Mapped[list["Video"]] = relationship(back_populates="author")` |
| `autoincrement=True` | не потрібно: `Mapped[int]` + `primary_key=True` вже так робить |

## Nullable

| оголошення | SQL |
| --- | --- |
| `age: Mapped[int]` | `INTEGER NOT NULL` |
| `age: Mapped[int \| None]` | `INTEGER` |
| `age: Mapped[Optional[int]]` | `INTEGER` — те саме, старий синтаксис |
| `mapped_column(nullable=True)` | перебиває анотацію, якщо дуже треба |

## Анотація → тип у базі

Перевірено на SQLAlchemy 2.0.52.

| Python | SQLite | Postgres |
| --- | --- | --- |
| `int` | `INTEGER` | `INTEGER` (а PK — `SERIAL`) |
| `str` | `VARCHAR` | `VARCHAR` |
| `bool` | `BOOLEAN` | `BOOLEAN` |
| `float` | `FLOAT` | `FLOAT` |
| `decimal.Decimal` | `NUMERIC` | `NUMERIC` |
| `datetime.datetime` | `DATETIME` | `TIMESTAMP WITHOUT TIME ZONE` |
| `datetime.date` | `DATE` | `DATE` |
| `datetime.time` | `TIME` | `TIME WITHOUT TIME ZONE` |
| `datetime.timedelta` | `DATETIME` ⚠️ | `INTERVAL` |
| `bytes` | `BLOB` | `BYTEA` |
| `uuid.UUID` | `CHAR(32)` | `UUID` |
| `enum.Enum`-підклас | `VARCHAR(n)` | нативний тип-enum |

`Mapped[str]` без розміру — це `VARCHAR` без довжини. Postgres і SQLite це
приймають, MySQL — ні. Ставте `String(n)`, якщо колись поїдете на MySQL.

## Явні типи

| тип | коли | приклад |
| --- | --- | --- |
| `String(n)` | рядок з обмеженням | `mapped_column(String(120))` |
| `Text` | довгий текст без ліміту | `mapped_column(Text)` |
| `Integer` | звичайне ціле | `mapped_column(Integer)` |
| `BigInteger` | великі id, лічильники | `mapped_column(BigInteger)` |
| `SmallInteger` | малі числа | `mapped_column(SmallInteger)` |
| `Numeric(10, 2)` | гроші — точно, без похибки float | `mapped_column(Numeric(10, 2))` |
| `Float` | наближені числа | `mapped_column(Float)` |
| `Boolean` | так/ні | `mapped_column(Boolean)` |
| `Date` / `Time` | тільки дата / тільки час | `mapped_column(Date)` |
| `DateTime(timezone=True)` | момент часу з таймзоною | `mapped_column(DateTime(timezone=True))` |
| `Interval` | тривалість | `mapped_column(Interval)` |
| `LargeBinary` | байти, файли | `mapped_column(LargeBinary)` |
| `Enum(PyEnum)` | фіксований набір значень | `mapped_column(Enum(Color))` |
| `Uuid` | UUID | `mapped_column(Uuid)` |
| `JSON` | довільна структура | `mapped_column(JSON)` |
| `JSONB` | те саме, але з індексами (Postgres) | `from sqlalchemy.dialects.postgresql import JSONB` |
| `ARRAY(Integer)` | масив (Postgres) | `from sqlalchemy.dialects.postgresql import ARRAY` |

Гроші тримайте в `Numeric`, а не `Float`: `0.1 + 0.2 != 0.3`.

## Аргументи `mapped_column()`

| аргумент | що робить | приклад |
| --- | --- | --- |
| `primary_key=True` | первинний ключ, автоінкремент сам | `mapped_column(primary_key=True)` |
| `nullable=` | перебиває анотацію | `mapped_column(nullable=True)` |
| `unique=True` | UNIQUE-обмеження | `mapped_column(String(120), unique=True)` |
| `index=True` | індекс; на FK — обов'язково | `mapped_column(ForeignKey("users.id"), index=True)` |
| `default=` | значення обчислює Python на INSERT | `mapped_column(default=0)` |
| `insert_default=` | те саме, явна назва | `mapped_column(insert_default=7)` |
| `server_default=` | значення обчислює база, пишеться в DDL | `mapped_column(server_default=func.now())` |
| `onupdate=` | Python перераховує на кожному UPDATE | `mapped_column(onupdate=datetime.now)` |
| `server_onupdate=` | те саме силами бази | `mapped_column(server_onupdate=FetchedValue())` |
| `ForeignKey(...)` | зв'язок на рівні бази | `mapped_column(ForeignKey("users.id", ondelete="CASCADE"))` |
| перший позиційний | інша назва колонки в базі | `mapped_column("db_col_name", String(10))` |
| `deferred=True` | не завантажувати, поки не звернуться | `mapped_column(Text, deferred=True)` |
| `comment=` | комент у схемі бази | `mapped_column(comment="ціна в копійках")` |
| `sort_order=` | порядок колонок у DDL | `mapped_column(sort_order=-10)` |
| `autoincrement=` | керувати вручну (рідко) | `mapped_column(autoincrement=False)` |
| `Computed("expr")` | GENERATED-колонка, рахує база | `mapped_column(Computed("price * 2"))` |
| `Identity()` | `GENERATED AS IDENTITY` замість SERIAL | `mapped_column(Identity())` |

### `default` проти `server_default`

```python
created: Mapped[datetime] = mapped_column(default=datetime.now)          # рахує Python
created: Mapped[datetime] = mapped_column(server_default=func.now())     # рахує база
```

`server_default` попадає в DDL, тому значення буде правильним навіть для рядків,
які вставили через psql, міграцію або `insert()`. `default` спрацьовує лише коли
рядок іде через SQLAlchemy.

Обидва застосовуються **на INSERT**, а не в момент створення об'єкта:

```python
video = Video(title="x")
video.views          # None, хоча в моделі default=0
session.add(video); session.flush()
video.views          # 0
```

## Обмеження

Одноколонкові — прямо в колонці. Багатоколонкові — у `__table_args__`.

```python
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(120), unique=True)
    age: Mapped[int] = mapped_column(index=True)

    __table_args__ = (
        CheckConstraint("age > 10 AND age < 90", name="ck_users_age"),
        UniqueConstraint("name", "email", name="uq_users_name_email"),
        Index("ix_users_name_age", "name", "age"),
    )
```

| обмеження | що робить |
| --- | --- |
| `CheckConstraint` | перевірка значень на рівні бази |
| `UniqueConstraint` | унікальність кількох колонок разом |
| `Index` | складений індекс |
| `PrimaryKeyConstraint` | складений PK |
| `ForeignKeyConstraint` | складений FK |

Складений первинний ключ — просто два `primary_key=True`:

```python
class VideoTag(Base):
    __tablename__ = "video_tag"
    video_id: Mapped[int] = mapped_column(ForeignKey("videos.id"), primary_key=True)
    tag_id: Mapped[int] = mapped_column(ForeignKey("tags.id"), primary_key=True)
```

## Щоб не повторювати те саме

`Annotated` — назвали тип раз, використовуєте всюди:

```python
str120 = Annotated[str, mapped_column(String(120))]
pk = Annotated[int, mapped_column(primary_key=True)]
money = Annotated[Decimal, mapped_column(Numeric(10, 2))]

class Product(Base):
    __tablename__ = "products"
    id: Mapped[pk]
    name: Mapped[str120]
    price: Mapped[money]
```

`type_annotation_map` — змінити тип для всього застосунку:

```python
class Base(DeclarativeBase):
    type_annotation_map = {
        str: String(60),                       # кожен Mapped[str] стане VARCHAR(60)
        datetime: DateTime(timezone=True),     # завжди з таймзоною
        dict: JSONB,                           # dict -> JSONB на Postgres
    }
```

## Колонки, яких немає в базі

| спосіб | що робить |
| --- | --- |
| `column_property` | SQL-вираз як атрибут, рахує база в кожному SELECT |
| `hybrid_property` | один метод, працює і в Python, і у `where()` |
| звичайний `@property` | тільки Python, у запитах недоступний |

```python
class Person(Base):
    __tablename__ = "person"

    id: Mapped[int] = mapped_column(primary_key=True)
    first: Mapped[str] = mapped_column(String(40))
    last: Mapped[str] = mapped_column(String(40))
    age: Mapped[int]

    full = column_property(first + " " + last)

    @hybrid_property
    def is_adult(self):
        return self.age >= 18
```

```python
person.full                                       # "Оксана Забужко"
person.is_adult                                   # True — рахує Python
select(Person).where(Person.is_adult)             # ...WHERE age >= 18 — рахує база
```
