class PortalAdminOverviewAPIView(APIView):
    authentication_classes = [PortalJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role != PortalIdentity.ROLE_ADMIN:
            raise PermissionDenied("Administrator access only.")
        attempts_total = PortalExamAttempt.objects.count()
        passed_total = PortalExamAttempt.objects.filter(passed=True).count()
        recent = PortalExamAttempt.objects.select_related(
            "student", "exam", "exam__course"
        ).order_by("-submitted_at")[:8]
        stats = {
            "students": PortalIdentity.objects.filter(
                role=PortalIdentity.ROLE_STUDENT
            ).exclude(email__iendswith="@test.invalid").count(),
            "courses": PortalCourse.objects.filter(is_active=True).count(),
            "enrolments": PortalEnrollment.objects.count(),
            "pending": PortalEnrollment.objects.filter(status=PortalEnrollment.PENDING).count(),
            "lessons": PortalLesson.objects.filter(is_active=True).count(),
            "exams": PortalExam.objects.filter(is_active=True).count(),
            "attempts": attempts_total,
            "passed": passed_total,
            "passRate": round(passed_total * 100 / attempts_total) if attempts_total else 0,
            "certificates": PortalCertificate.objects.count(),
            "pending_paystack_count": PortalPayment.objects.filter(status=PortalPayment.PENDING).count(),
            "pending_bank_payments_count": PortalPaymentSubmission.objects.filter(status=PortalPaymentSubmission.PENDING).count(),
            "submitted_practice_count": PortalPracticeSubmission.objects.filter(status="submitted").count(),
        }
        return Response({
            **stats,
            "stats": stats,
            "recentAttempts": [{
                "id": str(item.pk), "score": item.score, "passed": item.passed,
                "submitted_at": item.submitted_at,
                "exam_title": item.exam.title, "course_title": item.exam.course.title,
                "student_name": item.student.full_name or item.student.username,
            } for item in recent],
        })


    authentication_classes = [PortalJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role != PortalIdentity.ROLE_ADMIN:
            raise PermissionDenied("Administrator access only.")
        records = PortalIdentity.objects.filter(role=PortalIdentity.ROLE_STUDENT).annotate(
            enrollment_count=models.Count("enrollments")
        ).order_by("-created_at")[:100]
        return Response({"results": [{
            "user_id": str(item.pk),
            "email": item.email,
            "username": item.username,
            "full_name": item.full_name,
            "phone": item.phone,
            "role": item.role,
            "created_at": item.created_at,
            "enrollment_count": item.enrollment_count,
        } for item in records]})


class PortalAdminCourseInstructorAPIView(APIView):
    authentication_classes = [PortalJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role != PortalIdentity.ROLE_ADMIN:
            raise PermissionDenied("Administrator access only.")
        assignments = PortalCourseInstructor.objects.select_related("course", "instructor", "assigned_by")[:300]
        return Response({"results": [{
            "id": str(item.pk),
            "course_id": str(item.course_id),
            "course_title": item.course.title,
            "instructor_id": str(item.instructor_id),
            "instructor_name": item.instructor.full_name or item.instructor.username,
            "instructor_email": item.instructor.email,
            "assigned_at": item.created_at,
        } for item in assignments]})

    def post(self, request):
        if request.user.role != PortalIdentity.ROLE_ADMIN:
            raise PermissionDenied("Administrator access only.")
        course_id = request.data.get("course_id")
        instructor_id = request.data.get("instructor_id")
        course = PortalCourse.objects.filter(pk=course_id, is_active=True).first()
        instructor = PortalIdentity.objects.filter(pk=instructor_id, role=PortalIdentity.ROLE_INSTRUCTOR, is_active=True).first()
        if not course or not instructor:
            raise serializers.ValidationError({"detail": "Choose an active course and an active instructor account."})
        assignment, created = PortalCourseInstructor.objects.get_or_create(
            course=course, instructor=instructor, defaults={"assigned_by": request.user}
        )
        if created:
            PortalAuditLog.objects.create(
                actor=request.user, action="course.instructor_assigned",
                target_type="course_instructor", target_id=str(assignment.pk),
                metadata={"course_id": str(course.pk), "instructor_id": str(instructor.pk)},
            )
        return Response({"id": str(assignment.pk), "course_id": str(course.pk), "instructor_id": str(instructor.pk), "created": created}, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    def delete(self, request, assignment_id):
        if request.user.role != PortalIdentity.ROLE_ADMIN:
            raise PermissionDenied("Administrator access only.")
        assignment = PortalCourseInstructor.objects.filter(pk=assignment_id).first()
        if not assignment:
            raise NotFound("Instructor assignment not found.")
        course_id, instructor_id = str(assignment.course_id), str(assignment.instructor_id)
        PortalCourseInstructor.objects.filter(pk=assignment.pk).delete()
        PortalAuditLog.objects.create(
            actor=request.user, action="course.instructor_unassigned",
            target_type="course_instructor", target_id=str(assignment.pk),
            metadata={"course_id": course_id, "instructor_id": instructor_id},
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class PortalInstructorCoursesAPIView(APIView):
    authentication_classes = [PortalJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role != PortalIdentity.ROLE_INSTRUCTOR:
            raise PermissionDenied("Instructor access only.")
        courses = PortalCourse.objects.filter(
            instructor_assignments__instructor=request.user, is_active=True
        ).distinct().order_by("title")
        return Response({"results": [{
            "id": str(course.pk), "title": course.title,
            "description": course.description, "level": course.level,
            "students_count": PortalEnrollment.objects.filter(
                course=course, status__in=[PortalEnrollment.APPROVED, PortalEnrollment.COMPLETED]
            ).count(),
        } for course in courses]})


class PortalInstructorStudentListAPIView(APIView):
    authentication_classes = [PortalJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, course_id):
        if request.user.role != PortalIdentity.ROLE_INSTRUCTOR:
            raise PermissionDenied("Instructor access only.")
        assigned = PortalCourseInstructor.objects.filter(course_id=course_id, instructor=request.user).exists()
        if not assigned:
            raise PermissionDenied("This course is not assigned to your instructor account.")
        enrollments = PortalEnrollment.objects.filter(
            course_id=course_id, status__in=[PortalEnrollment.APPROVED, PortalEnrollment.COMPLETED]
        ).select_related("student")[:200]
        return Response({"results": [{
            "student_id": str(item.student_id),
            "full_name": item.student.full_name or item.student.username,
            "email": item.student.email,
            "enrollment_status": item.status,
        } for item in enrollments]})
