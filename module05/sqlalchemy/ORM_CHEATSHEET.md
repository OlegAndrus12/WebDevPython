# SQLAlchemy 2.0 ORM — довідник

Моделі: `User(id, name, email, age, bio, created_at)`, `Video(id, title, views, likes, uploaded_on, author_id)`, `Tag(id, name)`.
Зв'язки: `user.videos`, `video.author`, `video.tags`.

## Engine і сесія

| команда | що робить | приклад |
| --- | --- | --- |
| `create_engine(url)` | з'єднання з базою + пул | `engine = create_engine("sqlite:///app.db")` |
| `sessionmaker(engine)` | фабрика сесій, одна на застосунок | `SessionLocal = sessionmaker(engine)` |
| `Session(engine)` | одна сесія | `with Session(engine) as s: ...` |
| `expire_on_commit=False` | дозволяє читати об'єкт після `commit()` | `sessionmaker(engine, expire_on_commit=False)` |
| `echo=True` | друкує весь SQL | `create_engine(url, echo=True)` |
| `session.begin()` | commit на виході, rollback на помилці | `with Session(engine) as s, s.begin(): ...` |

## Модель

| команда | що робить | приклад |
| --- | --- | --- |
| `DeclarativeBase` | база для всіх моделей | `class Base(DeclarativeBase): pass` |
| `__tablename__` | ім'я таблиці | `__tablename__ = "users"` |
| `Mapped[int]` | колонка `NOT NULL` | `age: Mapped[int]` |
| `Mapped[str \| None]` | колонка nullable | `bio: Mapped[str \| None]` |
| `mapped_column(primary_key=True)` | PK, автоінкремент | `id: Mapped[int] = mapped_column(primary_key=True)` |
| `mapped_column(String(120))` | точний тип і довжина | `name: Mapped[str] = mapped_column(String(120))` |
| `unique=True` | UNIQUE-обмеження | `mapped_column(String(120), unique=True)` |
| `index=True` | індекс (обов'язково на FK) | `mapped_column(ForeignKey("users.id"), index=True)` |
| `default=` | значення обчислює Python на INSERT | `views: Mapped[int] = mapped_column(default=0)` |
| `server_default=` | значення обчислює база | `mapped_column(server_default=func.now())` |
| `ForeignKey(...)` | зв'язок на рівні бази | `ForeignKey("users.id", ondelete="CASCADE")` |
| `relationship(back_populates=)` | атрибут-зв'язок у Python | `videos: Mapped[list["Video"]] = relationship(back_populates="author")` |
| `cascade="all, delete-orphan"` | ORM видаляє дітей разом з батьком | `relationship(cascade="all, delete-orphan")` |
| `secondary=` | many-to-many через таблицю-звʼязку | `relationship(secondary=VideoTag.__table__)` |
| `__table_args__` | обмеження на рівні таблиці | `(CheckConstraint("age > 10"), Index("ix_a", "active", "age"))` |
| `metadata.create_all` | створити таблиці | `Base.metadata.create_all(engine)` |
| `metadata.drop_all` | видалити таблиці | `Base.metadata.drop_all(engine)` |

## Сесія

| команда | що робить | приклад |
| --- | --- | --- |
| `session.add(obj)` | поставити об'єкт у чергу на INSERT | `session.add(user)` |
| `session.add_all([...])` | те саме для кількох | `session.add_all([u1, u2])` |
| `session.delete(obj)` | у чергу на DELETE | `session.delete(user)` |
| `session.flush()` | надіслати SQL, транзакцію не закривати | `session.flush()` |
| `session.commit()` | надіслати SQL + завершити транзакцію | `session.commit()` |
| `session.rollback()` | скасувати все після останнього commit | `session.rollback()` |
| `session.close()` | звільнити з'єднання | `session.close()` |
| `session.refresh(obj)` | перечитати об'єкт з бази зараз | `session.refresh(user)` |
| `session.expire(obj)` | позначити застарілим, перечитає при доступі | `session.expire(user)` |
| `session.merge(obj)` | внести стан відірваного об'єкта в сесію | `user = session.merge(detached)` |
| `session.expunge(obj)` | вилучити з сесії, рядок не чіпати | `session.expunge(user)` |
| `session.new` / `.dirty` / `.deleted` | що в черзі (для відладки) | `len(session.dirty)` |
| `session.no_autoflush` | заборонити flush під час запиту | `with session.no_autoflush: ...` |

## CREATE

| команда | що робить | приклад |
| --- | --- | --- |
| `Model(...)` + `add` | один рядок | `session.add(User(name="Олена", age=31)); session.commit()` |
| `parent.children.append` | дитина, FK заповнюється сам | `user.videos.append(Video(title="ORM"))` |
| `child.parent = obj` | те саме з іншого боку | `video.author = user` |
| `insert(Model)` + список | масовий INSERT без об'єктів | `session.execute(insert(Video), [{"title": "A"}, {"title": "B"}])` |
| `.returning(col)` | дістати згенерований id | `session.execute(insert(Video).values(title="C").returning(Video.id)).scalar_one()` |

## Запит: побудова

| команда | що робить | приклад |
| --- | --- | --- |
| `select(Model)` | цілі сутності | `select(User)` |
| `select(col, col)` | окремі колонки | `select(User.name, User.age)` |
| `.where(...)` | WHERE; кома = AND | `select(User).where(User.age > 30, User.name.like("О%"))` |
| `.filter_by(**kw)` | скорочення для рівності | `select(User).filter_by(age=27)` |
| `.order_by(...)` | сортування | `select(User).order_by(User.age.desc(), User.name)` |
| `.limit(n)` / `.offset(n)` | пагінація | `select(User).limit(10).offset(20)` |
| `.distinct()` | DISTINCT | `select(User.age).distinct()` |
| `.join(...)` | INNER JOIN | `select(User).join(Video)` |
| `.outerjoin(...)` | LEFT JOIN | `select(User).outerjoin(Video)` |
| `.group_by(...)` | групування | `.group_by(User.id)` |
| `.having(...)` | фільтр груп | `.having(func.count(Video.id) >= 3)` |
| `.options(...)` | стратегія завантаження зв'язків | `select(User).options(selectinload(User.videos))` |
| `.subquery()` | підзапит як таблиця | `sub = select(...).group_by(...).subquery()` |
| `.scalar_subquery()` | підзапит як одне значення | `select(func.count(Video.id)).where(...).scalar_subquery()` |
| `aliased(Model)` | та сама таблиця двічі | `V = aliased(Video)` |
| `.union(...)` | UNION двох запитів | `select(...).union(select(...))` |

Statement незмінний: кожен метод повертає новий об'єкт, `stmt` залишається як був.

## Запит: результат

| команда | що робить | приклад |
| --- | --- | --- |
| `session.scalars(stmt)` | сутності, розпаковані | `session.scalars(select(User)).all()` → `[User, User]` |
| `session.execute(stmt)` | `Row`-кортежі | `session.execute(select(User.name, User.age)).all()` → `[("Олена", 31)]` |
| `session.scalar(stmt)` | одне значення або `None` | `session.scalar(select(func.count(User.id)))` → `8` |
| `session.get(Model, pk)` | один об'єкт за PK | `session.get(User, 1)` |
| `.all()` | список усіх | `session.scalars(stmt).all()` |
| `.first()` | перший або `None` | `session.scalars(stmt).first()` |
| `.one()` | рівно один, інакше виняток | `session.scalars(stmt).one()` |
| `.one_or_none()` | один або `None`, виняток якщо >1 | `session.scalars(stmt).one_or_none()` |
| `.scalar_one()` | одне значення, рівно один рядок | `session.execute(stmt).scalar_one()` |
| `.mappings()` | рядки як словники | `session.execute(stmt).mappings().all()` |
| `.unique()` | обов'язково після `joinedload` на колекції | `session.scalars(stmt).unique().all()` |
| `row._mapping` | один `Row` як словник | `dict(row._mapping)` |

`session.scalars(stmt)` — це те саме, що `session.execute(stmt).scalars()`: лишає тільку першу колонку.

## Фільтри (WHERE)

| команда | що робить | приклад |
| --- | --- | --- |
| `==` `!=` `>` `<` `>=` `<=` | порівняння | `User.age > 30` |
| `.between(a, b)` | BETWEEN | `User.age.between(20, 30)` |
| `.in_([...])` | IN, приймає й підзапит | `User.age.in_([22, 24])` |
| `.not_in([...])` | NOT IN | `User.age.not_in([22, 24])` |
| `.like("%x%")` | LIKE, з урахуванням регістру | `User.email.like("%gmail.com")` |
| `.ilike("x%")` | LIKE без урахування регістру | `User.name.ilike("ол%")` |
| `.startswith` / `.endswith` | префікс / суфікс | `User.name.startswith("Ір")` |
| `.contains("x")` | входження підрядка | `User.name.contains("ко")` |
| `.is_(None)` | IS NULL (не `is None`!) | `User.bio.is_(None)` |
| `.is_not(None)` | IS NOT NULL | `User.bio.is_not(None)` |
| `and_(a, b)` | AND (ніколи `and`) | `and_(User.age > 30, User.name.like("О%"))` |
| `or_(a, b)` | OR (ніколи `or`) | `or_(Video.views > 15000, Video.likes > 3000)` |
| `not_(a)` / `~a` | NOT, у дужках | `~Video.title.like("%район%")` |
| `func.length(col)` | будь-яка SQL-функція | `func.length(User.name) > 20` |
| `func.date(col)` | привести дату до дня | `func.date(Video.uploaded_on) == "2025-06-01"` |
| `.exists()` | EXISTS | `select(select(User.id).where(User.age > 100).exists())` |

`is None` Python обчислює сам і повертає `False` — запит стає завжди порожнім.

## Агрегації

| команда | що робить | приклад |
| --- | --- | --- |
| `func.count()` | кількість рядків | `select(func.count()).select_from(Video)` |
| `func.count(col)` | кількість не-NULL | `select(func.count(Video.id))` |
| `func.count(func.distinct(col))` | кількість унікальних | `select(func.count(func.distinct(Video.author_id)))` |
| `func.sum` / `func.avg` | сума / середнє | `select(func.sum(Video.views))` |
| `func.min` / `func.max` | мінімум / максимум | `select(func.max(Video.views))` |
| `func.round(x, n)` | округлення | `select(func.round(func.avg(Video.views), 1))` |
| `func.coalesce(x, y)` | заміна NULL | `select(func.coalesce(func.max(Video.views), 0))` |
| `.label("n")` | ім'я для виразу | `func.count(Video.id).label("n")` |
| `.order_by(desc("n"))` | сортування за label | `.order_by(desc("n"))` |
| `case((умова, x), else_=y)` | if всередині SQL | `func.sum(case((Video.views > 10000, 1), else_=0))` |

`WHERE` фільтрує рядки до групування, `HAVING` — групи після. Групуйте за PK (`group_by(User.id)`), а не за іменем.

## Зв'язки

| команда | що робить | приклад |
| --- | --- | --- |
| `user.videos` | колекція дітей (lazy) | `for v in user.videos: ...` |
| `video.author` | батько | `video.author.name` |
| `.any()` | EXISTS по колекції | `select(User).where(User.videos.any(Video.views > 15000))` |
| `~....any()` | немає жодної дитини | `select(User).where(~User.videos.any())` |
| `.has()` | EXISTS по одиночному зв'язку | `select(Video).where(Video.author.has(User.age < 25))` |
| `.append()` / `.remove()` | додати / прибрати звʼязок | `video.tags.append(tag)` |
| `ondelete="CASCADE"` | видаляє база, навіть незавантажене | на `ForeignKey` |
| `cascade="all, delete-orphan"` | видаляє ORM | на `relationship` |

`any()` і `has()` дають EXISTS — рядки не дублюються, на відміну від `join`.

## Завантаження (N+1)

| команда | що робить | приклад |
| --- | --- | --- |
| `selectinload` | один окремий SELECT на всю пачку | `select(User).options(selectinload(User.videos))` |
| `joinedload` | LEFT JOIN в тому ж запиті | `select(Video).options(joinedload(Video.author))` |
| ланцюжок | два рівні вглиб | `selectinload(User.videos).selectinload(Video.tags)` |
| `load_only` | тільки потрібні колонки | `select(User).options(load_only(User.name))` |
| `contains_eager` | заповнити зв'язок з уже наявного join | `select(User).join(User.videos).options(contains_eager(User.videos))` |
| `raiseload` | заборонити lazy-завантаження | `select(User).options(raiseload(User.videos))` |
| `lazy="selectin"` | стратегія за замовчуванням у моделі | `relationship(lazy="selectin")` |
| `lazy="raise"` | N+1 стає помилкою, а не тихим гальмом | `relationship(lazy="raise")` |

`.join(Video)` фільтрує, але **не** заповнює `user.videos` — потрібні і join, і `options()`.

## UPDATE

| команда | що робить | приклад |
| --- | --- | --- |
| присвоєння | один об'єкт | `user.age = 32; session.commit()` |
| `update(Model)` | багато рядків одним запитом | `session.execute(update(Video).where(Video.views < 100).values(views=Video.views + 1000))` |
| `update` + список | за первинними ключами | `session.execute(update(User), [{"id": 1, "age": 33}])` |
| `.returning(col)` | повернути змінене | `update(User).where(User.id == 1).values(age=50).returning(User.name)` |
| `result.rowcount` | скільки рядків зачепило | `result.rowcount` |

## DELETE

| команда | що робить | приклад |
| --- | --- | --- |
| `session.delete(obj)` | один об'єкт, з cascade | `session.delete(user); session.commit()` |
| `delete(Model)` | багато рядків одним запитом | `session.execute(delete(Video).where(Video.views < 200))` |

`update()`/`delete()` обходять ORM: ніякого `delete-orphan`, ніяких Python-`default=`, об'єкти в памʼяті не оновлюються. Тому FK і потребує `ondelete="CASCADE"`.
