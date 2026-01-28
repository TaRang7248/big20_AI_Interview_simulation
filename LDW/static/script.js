document.getElementById('get-question-btn').addEventListener('click', async () => {
    const questionBox = document.getElementById('question-box');
    const answerSection = document.getElementById('answer-section');
    const getBtn = document.getElementById('get-question-btn');
    const resultBox = document.getElementById('result-box');

    getBtn.disabled = true;
    questionBox.innerText = '질문 생성 중...';
    resultBox.style.display = 'none';

    try {
        const source = document.querySelector('input[name="source"]:checked').value;
        const response = await fetch(`/interview/question?type=${source}`);
        const data = await response.json();

        if (data.question) {
            questionBox.innerText = data.question;
            answerSection.style.display = 'block';
        } else {
            questionBox.innerText = '질문을 불러오는데 실패했습니다.';
        }
    } catch (error) {
        console.error(error);
        questionBox.innerText = '에러 발생: ' + error.message;
    } finally {
        getBtn.disabled = false;
    }
});

document.getElementById('submit-answer-btn').addEventListener('click', async () => {
    const question = document.getElementById('question-box').innerText;
    const answer = document.getElementById('user-answer').value;
    const submitBtn = document.getElementById('submit-answer-btn');
    const loadingMsg = document.getElementById('loading-msg');
    const resultBox = document.getElementById('result-box');

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
            document.getElementById('result-score').innerText = `점수: ${data.evaluation.score}점`;
            document.getElementById('result-feedback').innerText = `피드백: ${data.evaluation.feedback}`;
            document.getElementById('result-improvements').innerText = `개선사항: ${data.evaluation.improvements}`;
            resultBox.style.display = 'block';
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
