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

var RPC = function(channel, apis) {
    var fixedApis = Object.keys(apis).map(function(apiId) {
        var api = apis[apiId];
        api.args = api.args || [];
        api.kwargs = api.kwargs || {};
        return api;
    });
    var apisByName = fixedApis.reduce(function(state, cur) {
        state[cur.name] = cur;
        return state;
    });
    var getApiFunc = function(name) {
        var api = apisByName[apiName];
        return function(args, kwargs) {
            channel.send(api.uri, {args: args, kwargs: kwargs});
        }
    }

    return getApiFunc;
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

var ApplicationManager = function(channel) {
    var apps = {};
    var allServices = {};

    function sendMessage(app, operation, message) {
        var obj = {operation: operation, payload: message};
        app.iframe.contentWindow.postMessage(JSON.stringify(obj), '*');
    }

    function getHost(url) {
        var anchor = document.createElement('a');
        anchor.setAttribute('href', url);
        return anchor.hostname + ":" + anchor.port;
    }

    var operations = {
        "queue-receive-register": function(app, queueName) {
            queueName = app.service_queue_prefix + queueName;

            channel.register(queueName, function(obj) {
                sendMessage(app, "queue-message", {
                    queue: queueName,
                    data: obj
                });
            });
        },
        "queue-receive-unregister": function(app, queueName) {
            queueName = app.service_queue_prefix + queueName;
            channel.unregister(queueName);
        },
        "queue-send": function(app, obj) {
            if (!obj.absoluteQueue) {
                obj.queue = app.service_queue_prefix + obj.queue;
            }
            channel.send(obj.queue, obj.message);
        },
        "app-info": function(app, obj) {
            var service = allServices[getHost(app.url)];
            sendMessage(app, 'app-info', service)
        }
    };

    function globalMessageListener(e) {
        console.log("Received message from iframe: ", e);
        var obj = JSON.parse(e.data);
        var app = apps[getHost(e.origin)];
        var operation = operations[obj.operation];
        if (app === undefined || operation === undefined) {
            return;
        }
        operation(app, obj.payload);
    }

    return {
        register: function(app) {
            apps[getHost(app.url)] = app;
        },
        getMessageListener: function() {
            return globalMessageListener;
        },
        updateServices: function(obj) {
            Object.keys(obj).forEach(function(serviceKey) {
                var service = obj[serviceKey];
                Object.keys(service.apps).forEach(function(appKey) {
                    var app = service.apps[appKey];
                    allServices[getHost(app.url)] = service;
                });
            })
        },
    };
};

var ApplicationUIManager = function(selector, appManager) {
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

    function findAppElem(appId) {
        return $(selector + ' [data-appid~="' + appId + '"]')[0];
    }

    var appTemplate = Handlebars.compile($(selector + " ul").html());
    $(selector + " ul").html("");

    window.addEventListener('message', appManager.getMessageListener());

    return {
        "launch": function(app) {
            var appElem = findAppElem(app.id);
            if (appElem !== undefined) {
                sly.activate(appElem);
                return;
            }

            var html = appTemplate(app);
            var nodes = $.parseHTML($.trim(html));

            sly.add(nodes[0]);
            sly.activate(nodes[0]);

            app.iframe = nodes[0].getElementsByTagName("iframe")[0];

        },
        "close": function(app) {
            var appElem = findAppElem(app.id);
            if (appElem !== undefined) {
                sly.remove(appElem);
            }
        }
    };
}

var TopBar = function(selector) {
    setInterval(function() {
        $(selector).html(new Date().toISOString().replace(/[TZ]/g, " "));
    }, 1000);
}

var DockComponent = function(selector, onClick) {
    var template = Handlebars.compile($(selector).html());

    function addDockItem(selector, app) {
        var html = template(app);
        var duration = 100 + Math.random() * 1000;
        var dom = $(html.trim());

        dom.click(function() {
            onClick(app);
        });

        dom.appendTo(selector);
        dom.hide().fadeIn(duration);
    }

    var curItems = {};

    $(selector).html("");

    return {
        addApps: function(data) {
            var newItems = Object.keys(data).filter(function(key) {
                return !(key in curItems);
            });
            var html = newItems.map(function(key) {
                var app = data[key];
                app.icon = app.icon || "cog";
                addDockItem(selector, app);
                curItems[key] = app;
            });
        }
    }
};

var Shell = function(selector) {
    var socket = Socket("/shell", {});
    var channel = MessagingChannel(socket);


    var appManager = ApplicationManager(channel);
    var appUIManager = ApplicationUIManager("#oneperframe", appManager);
    var dock = DockComponent("#dock-contents", function(app) {
        appUIManager.launch(app);
        appManager.register(app);
    });
    var topbar = TopBar("#page-topbar");

    function handleAppListing(apps) {
        appManager.updateServices(apps);
        Object.keys(apps).forEach(function(appId) {
            var app = apps[appId];
            dock.addApps(app.apps);
        });
    }
    socket.register("dock_apps", handleAppListing);
    socket.send("list_apps", {});
}

$(document).ready(function() {
    var shell = Shell("#page-wrapper");
});
