Handlebars.registerHelper('equals', function(op1, op2, options) {
    return op1 == op2? options.fn(this): options.inverse(this);
});

var Socket = function(namespace, params) {
    params.listeners = params.listeners || {};
    params.initMsg = params.initMsg || 'first-dummy-message';

    console.log("Connecting to: " + namespace);
    var socket = io.connect('http://' + document.domain + ':' + location.port + namespace, {
        //transports: ['websocket']
        rememberTransport: false,
        forceNew: true
    });

    socket.on('connect', function(data) {
        socket.emit(params.initMsg, {});
    });

    var defaultListeners = {
        "socket_disconnect": function(data) {
            socket.disconnect();
        }
    }

    var listeners = Object.assign({}, params.listeners, defaultListeners);

    Object.keys(listeners).forEach(function(key) {
        var value = listeners[key];
        if (typeof value !== 'function') {
            return;
        }
        socket.on(key, value);
    });

    return {
        send: function(key, value) {
            socket.emit(key, value);
        },
        close: function() {
            socket.disconnect();
        },
        register: function(key, fn) {
            if (typeof fn !== 'function') {
                return false;
            }
            socket.on(key, fn)
        },
        unregister: function(key) {
            socket.off(key);
        }
    }
}

var MessagingChannel = function(socket) {
    var receivers = {};
    socket.register("messaging", function(obj) {
        if (receivers[obj.queue] !== undefined) {
            receivers[obj.queue](obj.data);
        }
    });

    return {
        register: function(queue, handler) {
            receivers[queue] = handler;
        },
        unregister: function(queue) {
            delete receivers[queue];
        },
        send: function(queue, obj) {
            socket.send("messaging", {queue: queue, data: obj});
        }
    }
};

var ApplicationRPC = function() {
    var rpcTemplate = Handlebars.compile($("#rpc-template").html());

    function buildRPCContent(socket, appInfo, $node) {
        var html = rpcTemplate(appInfo);
        $node.append(html).on('click', 'form [type=submit]', function() {
            var $form = $(this).closest('form');
            var api = appInfo.apis[$form.data("api-id")];
            var args = (api.args || []).map(function(arg) {
                if (arg.type == "toggle") {
                    return $("[name=" + arg.name + "]").is(":checked");
                } else if (arg.type == "number") {
                    return parseInt($("[name=" + arg.name + "]").val());
                }
                return $("[name=" + arg.name + "]").val();
            });
            var kwargsParams = Object.keys(api.kwargs || {});
            var kwargs = kwargsParams.reduce(function(state, cur) {
                if (api.kwargs[cur].type == "toggle") {
                    state[cur] = $("[name=" + cur + "]").is(":checked");
                } else if (api.kwargs[cur].type == "number") {
                    state[cur] = parseInt($("[name=" + cur + "]").val());
                } else {
                    state[cur] = $("[name=" + cur + "]").val();
                }
                return state;
            }, {});

            var data = {command: api.id};
            if (args.length) {
                data.args = args;
            }
            if (Object.keys(kwargs).length) {
                data.kwargs = kwargs;
            }
            socket.send("messaging", {data: data, uri: $form.data("uri")});
            console.log("Sent to uri: ", $form.data("uri"), ", data: ", data);
            return false;
        });
    };

    return {
        build: buildRPCContent,
    }
}

var DockComponent = function(selector, appManager) {
    var template = Handlebars.compile($(selector).html());

    function addDockItem(selector, service) {
        var html = template(service);
        var duration = 100 + Math.random() * 1000;
        var dom = $(html.trim());

        dom.click(function() {
            appManager.launch(service);
        });

        dom.appendTo(selector);
        dom.hide().fadeIn(duration);
    }

    var curItems = {};

    return {
        addItems: function(data) {
            $(selector).html("");
            var newItems = Object.keys(data).filter(function(key) {
                return !(key in curItems);
            });
            var html = newItems.map(function(key) {
                var service = data[key];
                service.icon = service.icon || "cog";
                addDockItem(selector, service);
                curItems[key] = service;
            });
        }
    }

}

var TopBar = function(selector) {
    setInterval(function() {
        $(selector).html(new Date().toISOString().replace(/[TZ]/g, " "));
    }, 1000);
}

var ApplicationManager = function(selector, socket) {
    var sly = new Sly(selector, {
        horizontal: 1,
        itemNav: 'forceCentered',
        smart: 1,
        activateMiddle: 1,
        mouseDragging: 1,
        touchDragging: 1,
        releaseSwing: 1,
        startAt: 0,
        scrollBy: 1,
        speed: 300,
        elasticBounds: 1,
        easing: 'easeOutExpo',
        dragHandle: 1,
        dynamicHandle: 1,
        clickBar: 1,
    }).init();

    var rpc_builder = ApplicationRPC();

    function findAppElem(appId) {
        return $(selector + ' [data-appid~="' + appId + '"]')[0];
    }


    function buildApplicationContent(appInfo, node) {
        if (appInfo.kind == "RPC") {
            var contentNode = $(node).find(".application-content");
            rpc_builder.build(socket, appInfo, contentNode);
        }
    }

    var appTemplate = Handlebars.compile($(selector + " ul").html());
    $(selector + " ul").html("");

    return {
        "launch": function(app) {
            var appElem = findAppElem(app.id);
            if (appElem !== undefined) {
                sly.activate(appElem);
                return;
            }

            var html = appTemplate(app);
            var nodes = $.parseHTML($.trim(html));
            buildApplicationContent(app, nodes[0]);

            sly.add(nodes[0]);
            sly.activate(nodes[0]);
        },
        "close": function(app) {
            var appElem = findAppElem(app.id);
            if (appElem !== undefined) {
                sly.remove(appElem);
            }
        }
    };
}

var Shell = function(selector) {
    var socket = Socket("/shell", {});

    var appManager = ApplicationManager("#oneperframe", socket);
    var dock = DockComponent("#dock-contents", appManager);
    var topbar = TopBar("#page-topbar");

    socket.register("dock_apps", dock.addItems);
    socket.send("list_apps", {});
}

$(document).ready(function() {
    var shell = Shell("#page-wrapper");
});
