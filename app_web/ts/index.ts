const outputElement = document.getElementById('user-output') as HTMLTextAreaElement;
if (!outputElement) {
	throw new Error('Could not find an element with the id "user-output"');
}
let resetOutput = true;
outputElement.textContent = 'Ask a question below...';

const inputElement = document.getElementById('user-input') as HTMLInputElement;
if (!inputElement) {
	throw new Error('Could not find an element with the id "user-input"');
}
const submitButtonElement = document.getElementById('submit') as HTMLButtonElement;
if (!submitButtonElement) {
	throw new Error('Could not find an element with the id "submit"');
}
const sessionIdElement = document.getElementById('session-id') as HTMLInputElement;

const logsElement = document.getElementById('logs') as HTMLTextAreaElement;
if (!logsElement) {
	throw new Error('Could not find an element with the id "logs"');
}

// submitButtonElement.addEventListener('click', () => {
// 	const input = inputElement.value ?? "";
// 	console.log(inputElement);
// 	const output = input.split('').reverse().join('');
// 	outputElement.textContent = output;
// });

async function getOrCreateSessionId() {
	const sessionId = window.location.hash.substring(1);
	if (sessionId !== "") {
		return sessionId;
	}
	const resp = await fetch('/api/sessions', {
		method: 'POST',
	});
	const body = await resp.json();
	window.location.hash = body.id;
	return body.id;
}

(async function () {
	const sessionId = await getOrCreateSessionId();
	sessionIdElement.innerText = sessionId;

	// const resp = await fetch(`/api/sessions/${sessionId}`);
	// const body = await resp.json();

	// create websocket connection to /api/sessions/:id/ws
	const ws = new WebSocket(`ws://${window.location.host}/api/sessions/${sessionId}`);
	ws.onmessage = (event) => {
		const message = JSON.parse(event.data);
		console.log("Got message", message);
		logsElement.textContent += JSON.stringify(message) + '\n\n';
		logsElement.scrollTop = logsElement.scrollHeight;


		if (resetOutput) {
			outputElement.textContent = '';
			resetOutput = false;
		}
		if (message.type === "TextMessage" || (message.type === "HandoffMessage" && message.source === "user")) {
			const source = message.source == "user" ? "You" : "Bot";
			if (outputElement.textContent !== '' && message.source === "user") {
				// add new line before user message (except for the first message)
				outputElement.textContent += '\n';
			}
			outputElement.textContent += `${source}: ${message.content}\n`;
		} else if(message.type === "TaskResult") {
			submitButtonElement.disabled = false;
		}
	}
	console.log("enable!")
	submitButtonElement.disabled = false;
	inputElement.focus();

	inputElement.addEventListener('keydown', (event) => {
		if (event.key === 'Enter') {
			submitButtonElement.click();
		}
	});
	submitButtonElement.addEventListener('click', () => {
		const input = inputElement.value ?? "";
		console.log("sending", input);
		ws.send(JSON.stringify({ content: input}));
		inputElement.value = '';
		submitButtonElement.disabled = true;
	});

	
})();