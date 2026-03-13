from flask import Blueprint, render_template, redirect, url_for
from flask_login import current_user
from flask.typing import ResponseReturnValue

public_bp = Blueprint('public', __name__)


@public_bp.route('/')
def welcome() -> ResponseReturnValue:
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    return render_template('welcome.html')


@public_bp.route('/about')
def about() -> ResponseReturnValue:
    return render_template('about.html')


@public_bp.route('/sobre')
def about_legacy() -> ResponseReturnValue:
    return redirect(url_for('public.about'), code=301)
