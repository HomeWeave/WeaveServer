import jinja2

class BaseView(object):
    def __init__(self):
        pass

    def render_template(self, path, **kwargs):
        loader = jinja2.FileSystemLoader('templates')
        env = jinja2.Environment(loader=loader)
        template = env.get_template(path)
        return template.render(**kwargs)

    def html(self):
        return render_template('simple.html', title="Hello!")

