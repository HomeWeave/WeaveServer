var socket = io.connect('http://' + document.domain + ':' + location.port + "/navigation");
socket.on('view', function(data) {
	console.log(data);
	alert("message received.");
});

$(document).ready(function() {
	socket.emit('request_view', {});
})