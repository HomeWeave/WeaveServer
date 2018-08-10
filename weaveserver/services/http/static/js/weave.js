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
    Vue.component('weave-loop', {
      template: '#template-loop',
      props: ['data']
    });
    Vue.component('vertical-layout', {
      template: '#template-vertical-layout',
      props: ['data']
    });
    Vue.component('header-3', {
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

function processUITemplate(template, item) {
    function evaluateTemplateData(template, context) {
        if (typeof template === "object" && Array.isArray(template)) {
            return template.map(function(item) {
                return evaluateTemplateData(item, context);
            });
        } else if (typeof template === "object") {
            if (template.__vartype && template.__expression) {
                switch (template.__vartype) {
                    case "context":
                        var expr = template.__expression;
                        return (expr.keys || []).reduce(function(state, value) {
                            return state[value];
                        }, context);
                    case "variables":
                        var expr = template.__expression;
                        return (expr.keys || []).reduce(function(state, value) {
                            return state[value];
                        }, app.variables);
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

    return evaluateTemplateData(template, item);
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
        action.data.args = action.data.args || [];
        action.data.kwargs = action.data.kwargs || {};
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
                if (state[value] == undefined) {
                    state[value] = {};
                }
                return state[value];
            }, app.$data);
            app.$set(obj, data.keys.slice(-1)[0],
                     evaluateTemplateData(data.value, context));
        }
        return $.Deferred().resolve(data).promise();
    }

    function action(data, context) {
        if (data.action) {
            fireAction(data.action, data.data);
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

    function fireAction(nameOrAction, overrideData) {
        if (typeof nameOrAction === 'object') {
            evaluateAll(nameOrAction, []);
        } else {
            var obj = actions[nameOrAction];
            if (obj !== undefined) {
                obj = JSON.parse(JSON.stringify(obj));

                (overrideData || []).forEach(function(override) {
                    var lastObj = (override.keys || []).slice(0, -1).reduce(function(state, value) {
                        if (state[value] == undefined) {
                            state[value] = {};
                        }
                        return state[value];
                    }, obj);
                    lastObj[override.keys.slice(-1)[0]] = override.value;
                });

                return evaluateAll(obj, []);
            }
        }
    }

    return {
        fire: fireAction
    }
}

function GenericApplication(selector, appData) {
    if (registerComponents.called === undefined) {
        registerComponents();
        registerComponents.called = true;
    }

    var variables = appData["$variables"] || {};
    var actions = appData["$actions"] || {};
    delete appData["$variables"];
    delete appData["$actions"];

    // Setup watch object for all variables and internal 'variables'.
    var watch = {};
    Object.keys(appData).forEach(function(key) {
        watch[key] = {handler: function(val) {}, deep: true};
    });

    var app = new Vue({
        template: "#template-all-components",
        data: {
            "variables": variables,
            "data": appData["$ui"]
        },
        watch: watch,
        methods: {
            processUITemplate: processUITemplate,
            fireEvent: function(obj) {
                appActions.fire(obj);
            }
        }
    });

    // Setup actions.
    var appActions = Actions(app, actions);
    delete app["$actions"];

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