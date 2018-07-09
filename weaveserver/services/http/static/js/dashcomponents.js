function registerComponents() {
    Vue.component('card-footer-status', {
      template: '#template-footer-status',
      props: ['footer']
    });
    Vue.component('all-components', {
      template: '#template-all-components',
      props: ['data']
    });
    Vue.component('weave-switch', {
      template: '#template-switch',
      props: ['data']
    });
    Vue.component('vertical-layout', {
      template: '#template-vertical-layout',
      props: ['data']
    });
    Vue.component('h3', {
      template: '#template-h3',
      props: ['data']
    });
    Vue.component('paragraph', {
      template: '#template-paragraph',
      props: ['data']
    });
    Vue.component('weave-button', {
      template: '#template-button',
      props: ['data'],
      methods: {
        "onClick": function(event) {
            this.$root.fireEvent(event);
        }
      }
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
            });
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
            }, app.$data);
            app.$set(obj, data.keys.slice(-1)[0],
                     evaluateTemplateData(data.value, context));
        }
        return $.Deferred().resolve(data).promise();
    }

    function action(data, context) {
        if (data.action) {
            fireAction(data.action);
        }
        return $.Deferred().resolve(null).promise();
    }

    var handlers = {
        $rpc: rpc,
        $store: store,
        $action: action
    };

    function evaluate(action, context) {
        var handler = handlers[action.type];
        if (handler === undefined) {
            console.log("Unknown action: ", action)
            return;
        }

        return handler(action, context);
    }

    function evaluateAll(actions, context) {
        function evaluateAction(action) {
            evaluate(action, context).then(function(result) {
                var contextCopy = JSON.parse(JSON.stringify(context));
                contextCopy.unshift(result);
                evaluateAll(action.success || [], contextCopy);
            });
        }
        actions.forEach(function(action) {
            evaluateAction(action, context);
        });
    }

    function fireAction(name) {
        var obj = actions[name];
        if (obj !== undefined) {
            return evaluateAll(obj, []);
        }
    }

    return {
        fire: fireAction
    }
}

function GenericCard(selector, options) {
    var variables = options.data["$variables"] || {};
    var actions = options.data["$actions"] || {};
    delete options.data["$variables"];
    delete options.data["$actions"];

    options.data = options.data || {};
    options.data.variables = variables;

    // Setup watch object for all variables and internal 'variables'.
    var watch = {};
    Object.keys(options.data).forEach(function(key) {
        watch[key] = {handler: function(val) {}, deep: true};
    });

    var app = new Vue({
        template: options.template,
        data: options.data,
        watch: watch
    });
    DEBUG_APPS.push(app);

    // Setup actions.
    var appActions = Actions(app, actions);
    delete options.data["$actions"];

    appActions.fire("$load");

    // Manually mount to so that we can append it.
    app.$mount();
    $(selector).append(app.$el);

    return {
        event: function(event) {
            appActions.fire(event);
        },
        unload: function() {
            return;
        }
    };
}

function SmallCard(selector, data) {
    var defaultData = {
        cardType: '',
        icon: {},
        title: '',
        content: '',
        footer: []
    };

    return GenericCard(selector, {
        template: "#template-small-card",
        data: Object.assign({}, defaultData, data)
    });
}

function MediumCard(selector, data) {
    var defaultData = {
        cardTitle: '',
        cardContent: [],
        cardType: '',
        icon: {},
        title: '',
        content: '',
        footer: []
    }

    return GenericCard(selector, {
        template: "#template-medium-card",
        data: Object.assign({}, defaultData, data)
    });
}
