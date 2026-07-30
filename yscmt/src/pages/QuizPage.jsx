import { useEffect, useState } from "react";
import quizService from "../services/quizService";

function QuizPage() {

  const [quiz, setQuiz] = useState(null);
  const [questions, setQuestions] = useState([]);
  const [answers, setAnswers] = useState({});

  useEffect(() => {
    loadQuiz();
  }, []);

  async function loadQuiz() {

    const quizzes = await quizService.getQuizzes();

    if (quizzes.length === 0) return;

    setQuiz(quizzes[0]);

    const allQuestions =
      await quizService.getQuestions();

    setQuestions(
      allQuestions.filter(
        q => q.quiz === quizzes[0].id
      )
    );
  }

  function choose(question, answer) {

    setAnswers({
      ...answers,
      [question]: answer
    });

  }

  async function submitQuiz() {

    const result =
      await quizService.submitQuiz({

        quiz: quiz.id,
        answers

      });

    alert(
      `Score: ${result.score}%`
    );

  }

  if (!quiz) return <h2>Loading quiz...</h2>;

  return (

    <div className="quiz-page">

      <h1>{quiz.title}</h1>

      {

        questions.map(question => (

          <div
            key={question.id}
            className="question-card"
          >

            <h3>{question.text}</h3>

            {

              ["A", "B", "C", "D"].map(letter => (

                <button

                  key={letter}

                  onClick={() =>
                    choose(question.id, letter)
                  }

                >

                  {
                    question[
                      `option_${letter.toLowerCase()}`
                    ]
                  }

                </button>

              ))

            }

          </div>

        ))

      }

      <button
        className="btn-primary"
        onClick={submitQuiz}
      >
        Submit Quiz
      </button>

    </div>

  );

}

export default QuizPage;
