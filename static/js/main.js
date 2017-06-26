



$(document).ready(function() {
	var socket = io.connect('http://' + document.domain + ':' + location.port + "/navigation", {
		
	});
	socket.on('connect', function(data) {
		socket.emit('request_view', {});
	});
	
	socket.on('view', function(data) {
		console.log("WS" + JSON.stringify(data));
		$("#page-wrapper").html(data.html);
	});

})