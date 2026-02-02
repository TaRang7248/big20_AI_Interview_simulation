let sessionId = null;
let currentQuestion = "";
let isFollowup = false;

async function startSession() {
    const username = document.getElementById("username").value;
    if (!username) return alert("이름을 입력해주세요");

    const res = await fetch("/api/start_session", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_name: username })
    });

    const data = await res.json();
    sessionId = data.session_id;

    document.getElementById("start-screen").classList.add("hidden");
    document.getElementById("interview-screen").classList.remove("hidden");

    getNextQuestion();
}

async function getNextQuestion() {
    showLoading(true);
    document.getElementById("submit-btn").disabled = false;
    document.getElementById("submit-btn").classList.remove("hidden");
    document.getElementById("next-btn").classList.add("hidden");
    document.getElementById("user-answer").value = "";
    document.getElementById("user-answer").disabled = false;

    isFollowup = false; // Reset for new question

    try {
        const res = await fetch("/api/get_question", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ session_id: sessionId })
        });
        const data = await res.json();
        currentQuestion = data.question;

        appendMessage("면접관", currentQuestion, "bot-message");
    } catch (e) {
        alert("질문을 가져오는 중 오류가 발생했습니다.");
    }
    showLoading(false);
}

async function submitAnswer() {
    const answer = document.getElementById("user-answer").value;
    if (!answer) return alert("답변을 입력해주세요");

    appendMessage("지원자", answer, "user-message");
    showLoading(true);

    try {
        const res = await fetch("/api/submit_answer", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                session_id: sessionId,
                question: currentQuestion,
                answer: answer,
                is_followup: isFollowup
            })
        });

        const data = await res.json();

        if (data.status === "followup") {
            appendMessage("면접관 (꼬리 질문)", data.question, "bot-message");
            if (data.feedback) {
                appendMessage("시스템", "이전 답변에 대한 피드백: " + data.feedback, "text-warning");
            }
            currentQuestion = data.question;
            isFollowup = true;
            document.getElementById("user-answer").value = ""; // Clear for follow-up
        } else {
            // Completed
            const evalResult = data.evaluation;
            const evalHtml = `
                <strong>점수:</strong> ${evalResult.score}/100 <br>
                <strong>결과:</strong> ${evalResult.pass_fail} <br>
                <strong>피드백:</strong> ${evalResult.feedback}
            `;
            appendMessage("시스템", evalHtml, "alert alert-info");

            document.getElementById("submit-btn").classList.add("hidden");
            document.getElementById("next-btn").classList.remove("hidden");
            document.getElementById("user-answer").disabled = true;
        }

    } catch (e) {
        console.error(e);
        alert("답변 제출 중 오류가 발생했습니다.");
    }
    showLoading(false);
}

function appendMessage(sender, text, className) {
    const chatHistory = document.getElementById("chat-history");
    const msgDiv = document.createElement("div");
    msgDiv.className = `message-box ${className}`;
    msgDiv.innerHTML = `<strong>${sender}:</strong> <div class="mt-2">${text}</div>`;
    chatHistory.appendChild(msgDiv);
    chatHistory.scrollTop = chatHistory.scrollHeight;
}

function showLoading(show) {
    document.getElementById("loading").style.display = show ? "block" : "none";
}
