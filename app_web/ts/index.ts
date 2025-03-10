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

const statusElement = document.getElementById('status') as HTMLTextAreaElement;
if (!statusElement) {
	throw new Error('Could not find an element with the id "status"');
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

	createWebSocket(sessionId);

})();

function createWebSocket(sessionId: any) {
	statusElement.innerText = "Connecting...";
	console.log("Connecting to WebSocket", sessionId);
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

			outputElement.scrollTop = outputElement.scrollHeight;

		} else if (message.type === "TaskResult") {
			submitButtonElement.disabled = false;
		}
	};
	ws.onclose = (event) => {
		console.log("WebSocket closed", event);
		resetOutput = true;
		outputElement.textContent += '\nconnection closed, retrying...\n';

		inputElement.removeEventListener('keydown', inputKeyDownHandler);
		submitButtonElement.removeEventListener('click', submitClickHandler);
		submitButtonElement.disabled = true;
		statusElement.innerText = "Disconnected";

		createWebSocket(sessionId);
	}

	submitButtonElement.disabled = false;
	inputElement.focus();
	inputElement.addEventListener('keydown', inputKeyDownHandler);

	submitButtonElement.addEventListener('click', submitClickHandler);
	statusElement.innerText = "Ready";


	function inputKeyDownHandler(ev: KeyboardEvent) {
		if (ev.key === 'Enter') {
			submitButtonElement.click();
		}
	}
	function submitClickHandler() {
		const input = inputElement.value ?? "";
		console.log("sending", input);
		ws.send(JSON.stringify({ content: input }));
		inputElement.value = '';
		submitButtonElement.disabled = true;
	}
}
