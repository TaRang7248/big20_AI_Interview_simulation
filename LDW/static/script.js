const startContainer = document.getElementById('start-container');
const interviewContainer = document.getElementById('interview-container');
const questionBox = document.getElementById('question-box');
const answerSection = document.getElementById('answer-section');
const resultBox = document.getElementById('result-box');
const startBtn = document.getElementById('start-interview-btn');
const submitBtn = document.getElementById('submit-answer-btn');
const nextBtn = document.getElementById('next-question-btn');
const userAnswer = document.getElementById('user-answer');
const loadingMsg = document.getElementById('loading-msg');

async function fetchQuestion() {
    questionBox.innerText = 'AI가 질문을 생성하고 있습니다...';
    answerSection.style.display = 'block';
    resultBox.style.display = 'none';
    userAnswer.value = '';
    submitBtn.disabled = true;

    try {
        const response = await fetch('/interview/question');
        const data = await response.json();

        if (data.question) {
            questionBox.innerText = data.question;
            submitBtn.disabled = false;
        } else {
            questionBox.innerText = '질문을 불러오는데 실패했습니다.';
        }
    } catch (error) {
        console.error(error);
        questionBox.innerText = '에러 발생: ' + error.message;
    }
}

startBtn.addEventListener('click', () => {
    startContainer.style.display = 'none';
    interviewContainer.style.display = 'block';
    fetchQuestion();
});

submitBtn.addEventListener('click', async () => {
    const question = questionBox.innerText;
    const answer = userAnswer.value;

    if (!answer.trim()) {
        alert('답변을 입력해주세요.');
        return;
    }

    submitBtn.disabled = true;
    loadingMsg.style.display = 'block';
    resultBox.style.display = 'none';

    try {
        const response = await fetch('/interview/answer', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question, answer })
        });

        const data = await response.json();

        if (data.evaluation) {
            document.getElementById('result-score').innerText = `종합 점수: ${data.evaluation.score}점`;
            document.getElementById('result-feedback').innerText = `면접관 피드백: ${data.evaluation.feedback}`;
            document.getElementById('result-improvements').innerText = `💡 Tip: ${data.evaluation.improvements}`;
            resultBox.style.display = 'block';
            answerSection.style.display = 'none';
        } else {
            alert('평가 결과를 가져오는데 실패했습니다.');
        }
    } catch (error) {
        console.error(error);
        alert('에러 발생: ' + error.message);
    } finally {
        submitBtn.disabled = false;
        loadingMsg.style.display = 'none';
    }
});

nextBtn.addEventListener('click', () => {
    fetchQuestion();
});
