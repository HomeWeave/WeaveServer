function registerComponents() {
    Vue.component('card-footer-status', {
      template: '#template-footer-status',
      props: ['footer']
    });
}

function Actions(app, actions) {
    function evaluateTemplateData(template, context) {
        if (typeof template === "object" && Array.isArray(template)) {
            return template.map(function(item) {
                return evaluateTemplateData(item, context);
            });
        } else if (typeof template === "object") {
            if (template.__vartype && template.__expression) {
                switch (template.__vartype) {
                    case "result":
                        var expr = template.__expression;
                        return (expr.keys || []).reduce(function(state, value) {
                            return state[value];
                        }, context[expr.index || 0]);
                    case "app":
                        var expr = template.__expression;
                        return (expr.keys || []).reduce(function(state, value) {
                            return state[value];
                        }, app);
                    default:
                        return null;
                }
            }
            var result = {};
            Object.keys(template).forEach(function(key) {
                result[key] = evaluateTemplateData(template[key], context);
            })
            return result;
        } else {
            return template;
        }
    }

    function rpc(action, context) {
        return $.ajax({
            url: "/api/rpc",
            type: 'post',
            contentType: 'application/json; charset=UTF-8',
            data: JSON.stringify(evaluateTemplateData(action.data, context))
        });
    }

    function store(data, context) {
        if (data.keys && data.keys.length) {
            var obj = (data.keys || []).slice(0, -1).reduce(function(state, value) {
                return state[value];
            }, app);
            obj[data.keys.slice(-1)[0]] = evaluateTemplateData(data.value, context);
        }
        return $.Deferred().resolve(data).promise();
    }

    var handlers = {rpc: rpc, store: store};

    function evaluate(action) {
        var handler = handlers[action.type];
        if (handler === undefined) {
            console.log("Unknown action: ", action)
            return;
        }
        
        return handler(action, null);
    }

    function evaluateAll(actions) {
        var promises = actions.map(evaluate);
        $.when.apply($, promises).then(function() {

        })
    }

    return {
        fire: function(name) {
            var obj = actions[name];
            if (obj !== undefined) {
                return evaluateAll(obj);
            }
        }
    }
}

function GenericCard(selector, options) {
    var app = new Vue({
        template: options.template,
        data: options.data
    });

    function mount() {
        app.$mount();
        var dom = app.$el;
        $(selector).append(dom);
    }

    return {
        load: function(data) {
            app.$actions = Actions(app, data["$actions"] || {});
            delete data["$actions"]

            Object.keys(data).forEach(function(key) {
                app[key] = data[key];
            });

            app.$actions.fire("$load");
            mount();
        }
    };
}

function SmallCard(selector) {
    return GenericCard(selector, {
        template: "#template-small-card",
        data: {
            cardType: '',
            icon: {},
            title: '',
            content: '',
            footer: []
        }
    });
}

function MediumCard(selector) {
    return GenericCard(selector, {
        template: "#template-medium-card",
        data: {
            cartTitle: '',
            cardContent: [],
            cardType: '',
            icon: {},
            title: '',
            content: '',
            footer: []
        }
    });
}