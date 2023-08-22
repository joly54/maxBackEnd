import json
import os
import os.path as op
import pprint

from flask import Flask, send_from_directory, request
from flask_admin import Admin
from flask_admin.contrib.fileadmin import FileAdmin
from flask_admin.contrib.sqla import ModelView
from flask_cors import CORS
from flask_migrate import Migrate
from flask_restful import Api, Resource
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import ForeignKey, func
from flask_babel import Babel
from flasgger import Swagger

app = Flask(__name__)
swagger = Swagger(app)
CORS(app, supports_credentials=True)
api = Api(app)
babel = Babel(app)
app.extensions['babel'] = babel
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///base.db"

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = "secretkey"
db = SQLAlchemy(app)
migrate = Migrate(app, db)
admin = Admin(app, template_mode='bootstrap4')
path = op.join(op.dirname(__file__), 'static')
admin.add_view(FileAdmin(path, '/static/', name='File Management'))
base_url = "http://127.0.0.1:5000/"
# make fluid layout
app.config['FLASK_ADMIN_FLUID_LAYOUT'] = True


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    brand = db.Column(db.String(80))
    name = db.Column(db.String(80))
    price = db.Column(db.Integer)
    description = db.Column(db.String(200))
    category = db.Column(db.String(200))

    def __repr__(self):
        return f"<Product {self.name} Id {self.id}>"


class Image(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.String(200), ForeignKey('product.id'))
    image = db.Column(db.String(200))

    product = db.relationship('Product', backref='images', lazy=True)


class HeaderImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.String(200), ForeignKey('product.id'))
    image = db.Column(db.String(200))

    product = db.relationship('Product', backref='header_images', lazy=True)


class Sizes(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.String(200), ForeignKey('product.id'))
    sizeName = db.Column(db.String(200))
    amountSize = db.Column(db.Integer)

    product = db.relationship('Product', backref='sizes', lazy=True)


class imageViews(ModelView):
    column_display_pk = True
    column_hide_backrefs = False
    column_list = ['product.id', 'product.name', 'image']
    form_columns = ['image', 'product']
    column_searchable_list = ['product.name', 'product.id']
    column_filters = ['product.name', 'product.id']


class HeaderView(ModelView):
    column_display_pk = True
    column_hide_backrefs = False
    column_list = ['product.id', 'product.name', 'image']
    form_columns = ['image', 'product']
    column_searchable_list = ['product.name', 'product.id']
    column_filters = ['product.name', 'product.id']


class SizesView(ModelView):
    column_display_pk = True
    column_hide_backrefs = False
    column_list = ['product.id', 'product.name', 'sizeName', 'amountSize']
    form_columns = ['sizeName', 'amountSize', 'product']
    column_searchable_list = ['product.name', 'product.id']
    column_filters = ['product.name', 'product.id']
    column_labels = dict(product_id='Product ID', product='Product Name', sizeName='Size Name',
                         amountSize='Amount Size')


admin.add_view(ModelView(Product, db.session))
admin.add_view(imageViews(Image, db.session))
admin.add_view(HeaderView(HeaderImage, db.session))
admin.add_view(SizesView(Sizes, db.session))


@app.route('/files/<path:path>')
def send_static_files(path):
    return send_from_directory('', path)


@app.route('/filldb')
def filldb():
    with open('bac.json', 'r') as f:
        data = json.load(f)
    for product in data:
        new_product = Product(
            name=product['name'],
            price=product['price'],
            description=product['description'],
            category="Missed")
        db.session.add(new_product)
        db.session.commit()
        new_image = Image(image=product['image'], product=new_product)
        db.session.add(new_image)
        db.session.commit()
    return {'result': 'success'}


class Products(Resource):
    def post(self):
        """
                ---
                tags:
                  - Products
                parameters:
                  - name: page
                    in: query
                    type: integer
                    description: Page number
                  - name: size
                    in: query
                    type: integer
                    description: Number of items per page
                responses:
                  200:
                    description: List of products
                """
        page = int(request.args.get('page', 1))
        size = int(request.args.get('size', 10))
        options = request.get_json()
        brands = Product.query.with_entities(Product.brand).distinct()
        #make list from brands
        barnds_lsit = [brand[0] for brand in brands]
        print(barnds_lsit)
        included_brands = options.get('included_brands', barnds_lsit)

        categories = Product.query.with_entities(Product.category).distinct()
        included_categories = options.get('included_categories', [category[0] for category in categories])

        sizes = Sizes.query.with_entities(Sizes.sizeName).distinct()
        included_sizes = options.get('included_sizes', [size[0] for size in sizes])

        max_price = options.get('max_price', Product.query.with_entities(func.max(Product.price)).scalar())
        min_price = options.get('min_price', Product.query.with_entities(func.min(Product.price)).scalar())

        sort_order = options.get('sort_order', 'abc')

        products = Product.query.filter(Product.brand.in_(included_brands),
                                        Product.category.in_(included_categories),
                                        Product.price.between(min_price, max_price),
                                        Sizes.sizeName.in_(included_sizes)).all()
        if sort_order == 'abc':
            products = sorted(products, key=lambda x: x.name)
        elif sort_order == 'price_desc':
            products = sorted(products, key=lambda x: x.price)
        elif sort_order == 'price':
            products = sorted(products, key=lambda x: x.price, reverse=True)

        products = products[(page - 1) * size:page * size]

        serialized_products = []
        for product in products:
            images = Image.query.filter_by(product_id=product.id).all()
            images = [image.image for image in images]
            header_image = HeaderImage.query.filter_by(product_id=product.id).all()
            header_image = [image.image for image in header_image]
            sizes_c = Sizes.query.filter_by(product_id=product.id).filter(Sizes.sizeName.in_(included_sizes), Sizes.amountSize > 0).all()
            if not sizes_c:
                continue
            else:
                sizes = Sizes.query.filter_by(product_id=product.id).all()
                serialized_product = {
                    'id': product.id,
                    "brand" : product.brand,
                    'name': product.name,
                    'price': product.price,
                    "description": product.description,
                    "images": images,
                    "header_image": header_image,
                    "sizes": [{"sizeName": size.sizeName, "amountSize": size.amountSize} for size in sizes],
                    "InStock": True if sizes else False,
                    "category": product.category,
                }
                serialized_products.append(serialized_product)

        return {
            "total": len(serialized_products),
            'products': serialized_products}


class GetProduct(Resource):
    def get(self, id):
        """
           ---
           tags:
             - Products
           parameters:
             - name: id
               in: path
               type: integer
               required: true
               description: Product ID
           responses:
             200:
               description: Product details
             404:
               description: Product not found
           """
        product = Product.query.filter_by(id=id).first()
        if product is None:
            return {'product': None}, 404

        images = Image.query.filter_by(product_id=product.id).all()
        images = [image.image for image in images]
        header_image = HeaderImage.query.filter_by(product_id=product.id).all()
        header_image = [image.image for image in header_image]
        sizes = Sizes.query.filter_by(product_id=product.id).all()
        serialized_product = {
            'id': product.id,
            'name': product.name,
            'price': product.price,
            "description": product.description,
            "images": images,
            "header_image": header_image,
            "sizes": [{"sizeName": size.sizeName, "amountSize": size.amountSize} for size in sizes],
            "InStock": True if sizes else False,
            "category": product.category,
        }
        return {'product': serialized_product}


class isExistSizes(Resource):


    def post(self):
        """
    Endpoint to check the existence of product sizes and their availability.

    This endpoint takes a list of product sizes and checks if each size exists for the given product
    and returns the availability count for each size.

    ---
    tags:
      - Products
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: array
          items:
            type: object
            properties:
              id:
                type: integer
                description: Product ID
              sizeName:
                type: string
                description: Name of the size
        description: List of product IDs and size names to check.
    responses:
      200:
        description: Availability details of requested sizes
        schema:
          type: array
          items:
            type: object
            properties:
              id:
                type: integer
                description: Product ID
              sizeName:
                type: string
                description: Name of the size
              count:
                type: integer
                description: Number of items available in this size.
      400:
        description: Invalid request data or missing required fields.
    """
        body = request.get_json()
        pprint.pprint(body)
        if not isinstance(body, list):
            return {'message': 'Invalid request data. Expected a list of sizes.'}, 400

        data = []

        for d in body:
            if 'id' not in d or 'sizeName' not in d:
                return {'message': 'Each size object must have "id" and "sizeName".'}, 400

            size = Sizes.query.filter_by(product_id=d['id'], sizeName=d['sizeName']).first()
            product = Product.query.filter_by(id=d['id']).first()
            if product is None:
                d['product'] = None
            else:
                d['product'] ={
                    'id': product.id,
                    'name': product.name,
                    'price': product.price,
                    "description": product.description,
                    "category": product.category,
                    "images": [image.image for image in Image.query.filter_by(product_id=product.id).all()],
                    "header_image": [image.image for image in HeaderImage.query.filter_by(product_id=product.id).all()],
                    "sizes": [{"sizeName": size.sizeName, "amountSize": size.amountSize} for size in Sizes.query.filter_by(product_id=product.id).all()],
                    "InStock": True if Sizes.query.filter_by(product_id=product.id).all() else False,
                }
            if size is None:
                d['totalCount'] = 0
            else:
                d['totalCount'] = size.amountSize
            data.append(d)

        return data, 200


api.add_resource(Products, '/products')
api.add_resource(GetProduct, '/product/<int:id>')
api.add_resource(isExistSizes, '/isExistSizes')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
