var Library = function(caja, appInfo) {
    var libraries = {
        "basic": {
            "template": function(template) {
                var compiled = Handlebars.compile(template);
                caja.markFunction(compiled);
                return compiled;
            },
            "Socket": function(params) {
                var sock = ViewSocket(appInfo.namespace, params);
                caja.markFunction(sock.send);
                return sock;
            },
            "alert": function() {
                alert("[" + appInfo.name + "]" + arguments[0])
            },
            "log": function() {
                 console.log.apply(console, arguments);
            }
        }
    };
    var allowed = ["basic"];
    var allFuncs = allowed.map(function(x) {
        return libraries[x];
    }).reduce(function(state, item) {
        Object.assign(state, item);
        return state;
    }, {});
    Object.keys(allFuncs).forEach(function(key) {
        var func = allFuncs[key];
        allFuncs[key] = caja.tame(caja.markFunction(func));
    });
    return allFuncs;
}


var ViewAnimator = {
    default: function(selector, html) {
        $(selector).html(html);
    },
    fadeIn: function(selector, html) {
        var obj = $(selector);
        obj.hide();
        obj.html(html);
        obj.fadeIn();
    },
    riseUp: function(selector, html) {
        var obj = $(selector);
        obj.css('opacity', 0);
        obj.html(html);
        obj.slideDown('slow').animate({ opacity: 1 }, { queue: false, duration: 'slow' });
    }
}


var ViewSocket = function(namespace, params) {
    params.listeners = params.listeners || {};
    params.initMsg = params.initMsg || 'first-dummy-message';

    console.log("Connecting to: " + namespace);
    var socket = io.connect('http://' + document.domain + ':' + location.port + namespace, {
        //transports: ['websocket']
        rememberTransport: false
    });

    socket.on('connect', function(data) {
        socket.emit(params.initMsg, {});
    });
    
    Object.keys(params.listeners).forEach(function(key) {
        var value = params.listeners[key];
        if (typeof value !== 'function') {
            return;
        }
        socket.on(key, value);
    });

    return {
        send: function(key, value) {
            socket.emit(key, value);
        }
    }
}

var ViewManager = function(selector) {
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
        return $(selector + ' li[data-appid~="' + appId + '"]')[0];
    }

    var appTemplate = Handlebars.compile($("#application-wrap-template").html());

    return {
        activateApp: function(appId) {
            var elem = findAppElem(appId);
            if (elem === undefined) {
                console.log("No app: " + appId + " to activate.");
                return false;
            }
            sly.activate(elem);
        },
        listApps: function() {
            return $(selector + " li[data-appid]").map(function() {
                return $(this).data("appid");
            });
        },
        addApp: function(appInfo, onLoadFunc) {
            var elem = findAppElem(appInfo.id);
            if (elem !== undefined) {
                sly.remove(elem);
            }

            var html = appTemplate(appInfo);
            var nodes = $.parseHTML($.trim(html));

            sly.add(nodes[0])

            var container = nodes[0].querySelector(".application-wrap");

            var cajaObj = Caja(appInfo, container);
            cajaObj.load(onLoadFunc);
            console.log("Application loaded:", appInfo.name);
        },
        removeApp: function(appId) {
            var elem = findAppElem(appInfo.id);
            if (elem === undefined) {
                return false;
            }
            sly.remove(elem);
            return true;
        }
    }
};

var Caja = function(appInfo, container) {
    var uriPolicy = {
        rewrite: function(x) { return x;}
    };

    return {
        load: function(onLoadFunc) {
            caja.load(container, caja.policy.net.ALL, function(frame) {
                frame.code("/", 'text/html', appInfo.html);
                frame.api(Library(caja, appInfo));
                frame.run();

                if (onLoadFunc !== undefined) {
                    onLoadFunc();
                }
            });
        }
    };
}

$(document).ready(function() {
    
    caja.initialize({
        es5Mode: true,
        cajaServer: 'https://caja.appspot.com/',
        debug: true
    });

    viewManager = ViewManager("#oneperframe");

    var socket = ViewSocket("/shell", {
        listeners: {
            "active_apps": function(data) {
                data.apps.forEach(function(app) {
                    viewManager.addApp(app);
                });
                viewManager.activateApp(data.activeAppId);
            },
            "launch_app": function(data) {
                viewManager.addApp(data, function() {
                    console.log(data);
                    viewManager.activateApp(data.id);
                });
            },
            "activate_app": function(data) {
                viewManager.activateApp(data.id);
            }
        },
        initMsg: 'get_active_apps'
    });
});
