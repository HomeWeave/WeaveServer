var App = function(callback) {
    var body = document.getElementsByTagName('body')[0];
    body.style.backgroundColor = "transparent";

    var queueReceivers = {};

    var operations = {
        "queue-message": function(data) {
            var receiver = queueReceivers[data.queue];
            if (receiver === undefined) {
                return;
            }
            receiver(data.data);
        },
        "app-info": function(data) {
            appInfo.rpcs = data.rpcs;
            appInfo.apps = data.apps;

            callback(funcs);
        }
    };

    window.addEventListener('message', function(e) {
        console.log("Incoming msg:", e);
        var msg = JSON.parse(e.data);
        var operation = operations[msg.operation];
        var payload = msg.payload;

        if (operation == undefined || payload == undefined) {
            return;
        }

        operation(payload);
    });

    function sendMessage(operation, message) {
        var obj = {operation: operation, payload: message};
        window.parent.postMessage(JSON.stringify(obj), '*');
    }

    var appInfo = {};

    sendMessage("app-info", null);

    var funcs = {
        rpc: function(name) {
            var rpc = Object.keys(appInfo.rpcs).map(function(key) {
                return appInfo.rpcs[key];
            }).filter(function(rpc) {
                return rpc.name == name;
            })[0];

            if (rpc === undefined) {
                return null;
            }

            return function(apiName) {
                var api = Object.keys(rpc.apis).map(function(key) {
                    return rpc.apis[key];
                }).filter(function(api) {
                    return api.name == apiName;
                })[0];

                if (api === undefined) {
                    return null;
                }
                return function(args, kwargs) {
                    args = args || [];
                    kwargs = kwargs || {};

                    var data = {command: api.id};
                    if (args.length) {
                        data.args = args;
                    }
                    if (Object.keys(kwargs).length) {
                        data.kwargs = kwargs;
                    }
                    sendMessage('queue-send', {
                        queue: rpc.uri,
                        message: data
                    });
                }
            }
        }
    }
};
