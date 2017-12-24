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
        }
    }
}

var DockComponent = function(selector) {
    var template = Handlebars.compile($(selector + " ul").html());

    function showDockItem(selector, html) {
        var duration = 100 + Math.random() * 500;
        $(html.trim()).hide().appendTo(selector).fadeIn(duration);
    }

    var socket = Socket("/dock", {
        initMsg: "list",
        listeners: {
            "dock_apps": function(data) {
                var ul = $(selector + " ul");
                ul.html("");
                var html = Object.keys(data).map(function(key) {
                    var service = data[key];
                    service.icon = service.icon || "cog";
                    var html = template(service);
                    showDockItem(selector + " ul", html);
                });
            }
        }
    });
}

var TopBar = function(selector) {
    setInterval(function() {
        $(selector).html(new Date().toISOString().replace(/[TZ]/g, " "));
    }, 1000);
}

var Shell = function(selector) {
    var socket = Socket("/shell", {});
    var dock = DockComponent("#dock-contents");
    var topbar = TopBar("#page-topbar");
}

$(document).ready(function() {
    var shell = Shell("#page-wrapper");
});
