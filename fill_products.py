from database import Product, get_session

products = [
    {
        "name": "Корм для активных кошек",
        "category": "cats",
        "subcategory": "active",
        "price": 1200,
        "description": "Полнорационный корм для активных кошек. Содержит витамины и минералы.",
        "image_path": "cat_active.jpg"
    },
    {
        "name": "Корм для стерилизованных кошек",
        "category": "cats",
        "subcategory": "sterilized",
        "price": 1300,
        "description": "Корм для стерилизованных кошек. Поддерживает здоровье мочевыводящих путей.",
        "image_path": "cat_sterilized.jpg"
    },
    {
        "name": "Корм для мелких пород собак",
        "category": "dogs",
        "subcategory": "small",
        "price": 1100,
        "description": "Корм для мелких пород собак. Легкоусвояемый и вкусный.",
        "image_path": "dog_small.jpg"
    },
    {
        "name": "Корм для крупных и средних пород собак",
        "category": "dogs",
        "subcategory": "big",
        "price": 1500,
        "description": "Корм для крупных и средних пород собак. Содержит глюкозамин для суставов.",
        "image_path": "dog_big.jpg"
    },
    {
        "name": "Корм для средних и крупных пород собак",
        "category": "dogs",
        "subcategory": "medium_big",
        "price": 1400,
        "description": "Корм для средних и крупных пород собак. Баланс белков и жиров.",
        "image_path": "dog_medium_big.jpg"
    }
]

with get_session() as session:
    for prod in products:
        exists = session.query(Product).filter_by(
            name=prod["name"], category=prod["category"], subcategory=prod["subcategory"]
        ).first()
        if not exists:
            product = Product(**prod)
            session.add(product)
    session.commit()
print("Товары успешно добавлены!")
