import { useState } from "react";
import progressService from "../../services/progressService";

export default function CoursePlayer() {

  const [lesson, setLesson] = useState<any>(null);

  async function completeLesson() {

    await progressService.completeLesson(lesson.id);

    alert("Lesson completed.");

  }

  return (

    <div>

      <h1>{lesson?.title}</h1>

      <iframe
        width="100%"
        height="500"
        src={lesson?.video_url}
      />

      <button
        onClick={completeLesson}
      >
        Mark Complete
      </button>

    </div>

  );

}
