function registerComponents() {
    Vue.component('card-footer-status', {
      template: '#template-footer-status',
      props: ['footer']
    });
}

function Actions(app, actions) {
    function rpc(action, previousResult) {
        return $.ajax({
            url: "/api/rpc",
            type: 'post',
            contentType: 'application/json; charset=UTF-8',
            data: JSON.stringify(action.data)
        });
    }

    function store(data, previousResult) {
        app[data.key] = data.value;
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