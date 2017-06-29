"""
Contains BaseView that acts as a base class for all views. Uses jinja2 for
templating.
"""
import jinja2


class BaseView(object):
    """
    Base class for all the views.
    """
    def __init__(self):
        pass

    def render_template(self, path, **kwargs):
        loader = jinja2.FileSystemLoader('templates')
        env = jinja2.Environment(loader=loader)
        template = env.get_template(path)
        return template.render(**kwargs)

    def html(self):
        """
        Returns an HTML string with simple.html as template, and title as "Hello!"
        """
        return self.render_template('simple.html', title="Hello!")
