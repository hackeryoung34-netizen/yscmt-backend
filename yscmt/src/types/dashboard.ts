export interface DashboardData {
  student: string;

  overview: {
    total_courses: number;
    courses_enrolled: number;
    total_lessons: number;
    completed_lessons: number;
    progress: number;
  };

  quizzes: {
    attempts: number;
    completed: number;
  };

  certificates: number;

  payments: {
    count: number;
    total_paid: number;
  };

  recent_courses: {
    course__name: string;
    enrolled_at: string;
  }[];
}
