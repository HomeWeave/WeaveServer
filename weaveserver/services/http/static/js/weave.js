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
    Vue.component('weave-condition', {
      template: '#template-condition',
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

function ExpressionEvaluator(app, contextObj, options) {
    var defaultOptions = {
        assumeIntermediateObjects: false
    }

    var curOpts = Object.assign({}, defaultOptions, options);
    contextObj.variables = app.variables;
    return function evaluate(template) {
        if (typeof template === "object" && Array.isArray(template)) {
            return template.map(function(item) {
                return evaluate(item);
            });
        } else if (typeof template === "object") {
            if (template.__vartype && template.__expression) {
                var context = contextObj[template.__vartype];
                if (context === undefined) {
                    return null;
                }

                return (template.__expression.keys || []).reduce(function(state, value) {
                    if (curOpts.assumeIntermediateObjects && state[value] == undefined) {
                        state[value] = {};
                    }
                    return state[value];
                }, context);
            }
            var result = {};
            Object.keys(template).forEach(function(key) {
                result[key] = evaluate(template[key], context);
            });
            return result;
        } else {
            return template;
        }
    };
}

function ConditionEvaluator(app, context, options) {
    var expressionEvaluator = ExpressionEvaluator(app, context, options);

    function equals(obj1, obj2) {
        return _.isEqual(expressionEvaluator(obj1), expressionEvaluator(obj2));
    }

    var comparators = {
        "eq": {fn: equals, args: 2}
    };

    return function evaluate(condition) {
        var comparatorInfo = comparators[condition.op];
        if (comparatorInfo === undefined) {
            console.log("Invalid operator: " + condition.op);
            return false;
        }
        if (comparatorInfo.args != condition.operands.length) {
            console.log("Bad number of operands")
            return false;
        }

        return comparatorInfo.fn.apply(null, condition.operands);
    };
}

function Actions(app, actions) {
    function rpc(action, context) {
        action.data.args = action.data.args || [];
        action.data.kwargs = action.data.kwargs || {};
        var data = ExpressionEvaluator(app, {result: context})(action.data);
        return $.ajax({
            url: "/api/rpc",
            type: 'post',
            contentType: 'application/json; charset=UTF-8',
            data: JSON.stringify(data)
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
            var result = ExpressionEvaluator(app, {result: context})(data.value);
            app.$set(obj, data.keys.slice(-1)[0], result);
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
            processUITemplate: function(template, item) {
                return ExpressionEvaluator(app, {context: item})(template);
            },
            evaluateCondition: function(condition) {
                var res = ConditionEvaluator(app, {})(condition);
                return res;
            },
            fireEvent: function(obj) {
                appActions.fire(obj);
            }
        }
    });
    DEBUG = app;

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
