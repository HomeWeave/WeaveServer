var App = function(callback) {
    var body = document.getElementsByTagName('body')[0];
    body.style.backgroundColor = "transparent";

    var queueReceivers = {};
    var rpcWaiters = {};

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
        },
        'rpc': function (data) {
            var callback = rpcWaiters[data.id];
            if (callback === undefined) {
                return;
            }
            callback(data.result);
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
        queue: function(queueName, handler) {
            queueReceivers[queueName] = handler;
            sendMessage('queue-receive-register', queueName);
        },
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
                return function(args, kwargs, callback) {
                    args = args || [];
                    kwargs = kwargs || {};

                    var data = {func: api.name, uri: rpc.uri};
                    if (args.length) {
                        data.args = args;
                    }
                    if (Object.keys(kwargs).length) {
                        data.kwargs = kwargs;
                    }

                    var id = "random-" + Math.random();
                    var obj = {
                        "id": id,
                        "rpc": data
                    };
                    rpcWaiters[id] = callback;
                    sendMessage('rpc', obj);
                }
            }
        }
    }
};
