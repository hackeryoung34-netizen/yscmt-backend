import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";

import lessonService from "../services/lessonService";

function CoursePlayer() {
    const { id } = useParams();
    const navigate = useNavigate();

    const [lessons, setLessons] = useState([]);
    const [currentLesson, setCurrentLesson] = useState(null);

    useEffect(() => {
        loadLessons();
    }, [id]);

    async function loadLessons() {
        try {
            const data = await lessonService.getLessons(id);

            setLessons(data);

            if (data.length > 0) {
                setCurrentLesson(data[0]);
            }
        } catch (error) {
            console.error(error);
        }
    }

    async function markComplete() {
        if (!currentLesson) return;

        try {
            await lessonService.markCompleted(currentLesson.id);

            alert("Lesson completed successfully!");

            const currentIndex = lessons.findIndex(
                lesson => lesson.id === currentLesson.id
            );

            if (currentIndex < lessons.length - 1) {
                setCurrentLesson(
                    lessons[currentIndex + 1]
                );
            } else {
                alert(
                    "🎉 Congratulations! You have completed all lessons in this course."
                );
            }
        } catch (error) {
            console.error(error);
            alert("Unable to mark lesson as completed.");
        }
    }

    return (
        <section className="course-player">

            <aside className="lesson-sidebar">

                <h2>Course Lessons</h2>

                {lessons.map((lesson) => (

                    <button
                        key={lesson.id}
                        className={
                            currentLesson?.id === lesson.id
                                ? "lesson-item active"
                                : "lesson-item"
                        }
                        onClick={() => setCurrentLesson(lesson)}
                    >
                        {lesson.title}
                    </button>

                ))}

            </aside>

            <main className="lesson-content">

                {currentLesson ? (

                    <>

                        <h1>{currentLesson.title}</h1>

                        {currentLesson.video_url && (

                            <iframe
                                src={currentLesson.video_url}
                                title={currentLesson.title}
                                width="100%"
                                height="500"
                                frameBorder="0"
                                allowFullScreen
                                style={{
                                    border: "none",
                                    borderRadius: "12px",
                                    marginBottom: "30px",
                                }}
                            />

                        )}

                        <p>{currentLesson.description}</p>

                        <div
                            dangerouslySetInnerHTML={{
                                __html: currentLesson.content,
                            }}
                        />

                        {currentLesson.resource && (

                            <a
                                href={currentLesson.resource}
                                target="_blank"
                                rel="noreferrer"
                                className="btn-primary"
                                style={{ display: "inline-block", marginTop: "20px" }}
                            >
                                📄 Download Lesson Resource
                            </a>

                        )}

                        <div
                            style={{
                                display: "flex",
                                gap: "15px",
                                marginTop: "30px",
                                flexWrap: "wrap",
                            }}
                        >

                            <button
                                className="btn-primary"
                                onClick={markComplete}
                            >
                                ✓ Mark Lesson Complete
                            </button>

                            <button
                                className="btn-secondary"
                                onClick={() =>
                                    navigate(`/quiz/${currentLesson.course}`)
                                }
                            >
                                🧪 Take Quiz
                            </button>

                        </div>

                    </>

                ) : (

                    <h2>No lessons available.</h2>

                )}

            </main>

        </section>
    );
}

export default CoursePlayer;
