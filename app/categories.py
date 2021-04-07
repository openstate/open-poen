from flask import flash, redirect, url_for
from sqlalchemy.exc import IntegrityError

from app import app, db
from app.forms import CategoryForm
from app.models import Category
from app.util import flash_form_errors


def return_redirect(project_id, subproject_id):
    # redirect back to clear form data
    if subproject_id:
        return redirect(
            url_for(
                'subproject',
                project_id=project_id,
                subproject_id=subproject_id
            )
        )

    return redirect(
        url_for(
            'index'
        )
    )


# Process filled in category form
def process_category_form(request):
    category_form = CategoryForm(prefix="category_form")

    # Check whether the category form is for a project or subproject
    project_id = category_form.project_id.data
    subproject_id = 0
    if category_form.subproject_id.data:
        subproject_id = category_form.subproject_id.data
    app.logger.info(project_id)
    app.logger.info(subproject_id)

    # Remove category
    if category_form.remove.data:
        Category.query.filter_by(id=category_form.id.data).delete()
        db.session.commit()
        flash(
            '<span class="text-default-green">Categorie "%s" is verwijderd</span>' % (
                category_form.name.data
            )
        )
        return return_redirect(project_id, subproject_id)

    # Update or save category
    if category_form.validate_on_submit():
        category = Category.query.filter_by(id=category_form.id.data)
        if len(category.all()):
            category.update({'name': category_form.name.data})
            db.session.commit()
            flash(
                '<span class="text-default-green">Categorie is bijgewerkt</span>'
            )
        else:
            try:
                if subproject_id:
                    category = Category(
                        name=category_form.name.data,
                        subproject_id=subproject_id
                    )
                else:
                    category = Category(
                        name=category_form.name.data,
                        project_id=project_id
                    )
                db.session.add(category)
                db.session.commit()
                flash(
                    '<span class="text-default-green">Categorie '
                    f'{category_form.name.data} is toegevoegd</span>'
                )
            except IntegrityError as e:
                db.session().rollback()
                app.logger.error(repr(e))
                flash(
                    '<span class="text-default-red">Categorie toevoegen mislukt: naam '
                    f'"{category_form.name.data}" bestaat al, kies een '
                    'andere naam<span>'
                )

        # redirect back to clear form data
        return return_redirect(project_id, subproject_id)
    else:
        flash_form_errors(category_form, request)
