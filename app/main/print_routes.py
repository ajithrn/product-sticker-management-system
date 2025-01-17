from flask import render_template, redirect, url_for, flash, request, jsonify, send_file, current_app
from flask_login import login_required, current_user
from datetime import datetime, timedelta
import os

from app import db
from app.models import Product, PrintJob
from app.forms import SingleProductPrintForm, PrintForm
from app.sticker import Sticker, create_stickers_pdf

from . import main
from .products import generate_batch_number

@main.route('/print', methods=['GET', 'POST'])
@login_required
def multi_product_print_view():
    """
    View function for printing stickers for multiple products.
    """
    form = PrintForm()
    selected_products = []

    if request.method == 'POST':
        if form.add_product.data:
            product_id = request.form.get('product_id')
            product = Product.query.get(product_id)
            selected_products.append({
                'id': product.id,
                'name': product.name,
                'quantity': form.quantity.data,
                'mfg_date': form.mfg_date.data,
                'exp_date': form.exp_date.data
            })

    return render_template('multi_print.html', form=form, selected_products=selected_products)

@main.route('/print/<int:product_id>', methods=['GET', 'POST'])
@login_required
def print_stickers_for_product(product_id):
    """
    View function for printing stickers for a specific product.
    """
    form = SingleProductPrintForm()
    product = Product.query.get(product_id)
    form.product_id.choices = [(product.id, product.name)]

    if request.method == 'POST' and form.validate_on_submit():
        quantity = form.quantity.data

        mfg_date = form.mfg_date.data or datetime.now().date()
        exp_date = form.exp_date.data or mfg_date + timedelta(days=product.shelf_life)

        batch_number = generate_batch_number(product.name)

        stickers = [
            Sticker(
                product_name=product.name,
                rate=str(product.rate),  # Convert Decimal to string for sticker
                mfg_date=mfg_date,
                exp_date=exp_date,
                net_weight=product.net_weight,
                ingredients=product.ingredients,
                nutritional_facts=product.nutritional_facts,
                batch_number=batch_number,
                allergen_information=product.allergen_information
            )
            for _ in range(quantity)
        ]

        # Create the PDF file
        pdf_path = create_stickers_pdf(stickers)

        # Create print job with proper relationships
        print_job = PrintJob(
            product_id=product.id,
            user_id=current_user.id,
            quantity=quantity,
            batch_number=batch_number
        )
        db.session.add(print_job)
        db.session.commit()

        return jsonify({
            'message': 'Stickers has been generated successfully!',
            'pdf_url': url_for('main.sticker_preview')
        })

    if request.method == 'GET':
        form.product_id.data = product.id
        form.mfg_date.data = datetime.now().date()
        form.exp_date.data = datetime.now().date() + timedelta(days=product.shelf_life)

    return render_template('print.html', form=form)

@main.route('/print_stickers', methods=['POST'])
@login_required
def print_stickers_route():
    """
    Handles AJAX request to print stickers for multiple products.
    """
    selected_products = request.get_json()
    all_stickers = []  # Create a list to hold stickers from all products

    if selected_products:
        for product_data in selected_products:
            product_id = product_data.get('id')
            product = Product.query.get(product_id)
            quantity = int(product_data.get('quantity'))
            mfg_date = datetime.strptime(product_data.get('mfg_date'), '%Y-%m-%d').date()
            exp_date = datetime.strptime(product_data.get('exp_date'), '%Y-%m-%d').date()

            batch_number = generate_batch_number(product.name)

            # Generate stickers for the current product
            stickers = [
                Sticker(
                    product_name=product.name,
                    rate=str(product.rate),  # Convert Decimal to string for sticker
                    mfg_date=mfg_date,
                    exp_date=exp_date,
                    net_weight=product.net_weight,
                    ingredients=product.ingredients,
                    nutritional_facts=product.nutritional_facts,
                    batch_number=batch_number,
                    allergen_information=product.allergen_information
                )
                for _ in range(quantity)
            ]

            # Append the generated stickers to the all_stickers list
            all_stickers.extend(stickers)

            # Create print job with proper relationships
            print_job = PrintJob(
                product_id=product.id,
                user_id=current_user.id,
                quantity=quantity,
                batch_number=batch_number
            )
            db.session.add(print_job)

        db.session.commit()
        
        # Create PDF for all stickers
        pdf_path = create_stickers_pdf(all_stickers)

        return jsonify({
            'message': 'Stickers has been generated successfully!',
            'pdf_url': url_for('main.sticker_preview')
        })

    return jsonify({'message': 'No products selected for printing. Please select at least one product.'})

@main.route('/sticker_preview')
@login_required
def sticker_preview():
    """
    Serve the generated PDF file inline.
    """
    pdf_path = os.path.join(current_app.root_path, '..', 'stickers_to_print.pdf')
    return send_file(pdf_path, mimetype='application/pdf')
