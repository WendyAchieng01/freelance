
CATEGORY_CHOICES = [
    ('data_entry', 'Data Entry'),
    ('translation', 'Translation'),
    ('transcription', 'Transcription and Captioning'),
    ('graphics', 'Graphics & Design'),
    ('writing', 'Writing and Editing'),
    ('web_dev', 'Web and App Development'),
    ('project_mgmt', 'IT Project Management'),
    ('testing', 'Software Testing'),
    ('virtual_assist', 'Virtual Assistance'),
    ('social_media', 'Social Media Management'),
    ('ai_training', 'AI Model Training'),
    ('seo', 'SEO and SEM'),
    ('content_creation', 'Content Creation'),
    ('video_editing', 'Video Editing'),
    ('photo_editing', 'Photo Editing'),
    ('customer_support', 'Customer Support'),
    ('sales', 'Sales and Lead Generation'),
    ('marketing', 'Digital Marketing'),
    ('cybersecurity', 'Cybersecurity'),
    ('qa', 'Quality Assurance'),
    ('cloud_services', 'Cloud Services'),
    ('blockchain', 'Blockchain Development'),
    ('devops', 'DevOps'),
    ('database_admin', 'Database Administration'),
    ('finance', 'Finance and Accounting'),
    ('legal', 'Legal Services'),
    ('hr', 'Human Resources'),
    ('training', 'Corporate Training'),
    ('game_dev', 'Game Development'),
    ('mobile_dev', 'Mobile App Development'),
    ('animation', '2D/3D Animation'),
    ('voice_over', 'Voice Over'),
    ('research', 'Research and Analysis'),
    ('data_science', 'Data Science & Analytics'),
    ('ai_dev', 'AI & Machine Learning Development'),
    ('network_admin', 'Network Administration'),
    ('system_admin', 'System Administration'),
    ('ecommerce', 'E-commerce Management'),
    ('product_mgmt', 'Product Management'),
    ('business_consulting', 'Business Consulting'),
    ('ux_ui', 'UX/UI Design'),
    ('scripting', 'Scripting and Automation'),
    ('tech_support', 'Technical Support'),
    ('procurement', 'Procurement and Logistics'),
]


# Job status choices for Job model
JOB_STATUS_CHOICES = (
    ('open', 'Open'),
    ('in_progress', 'In Progress'),
    ('completed', 'Completed'),
)

# Application status choices for Response model
APPLICATION_STATUS_CHOICES = (
    ('submitted', 'Submitted'),
    ('under_review', 'Under Review'),
    ('accepted', 'Accepted'),
    ('rejected', 'Rejected'),
)

# Allowed status filter options for JobViewSet
ALLOWED_STATUS_FILTERS = {
    'all_users': JOB_STATUS_CHOICES, 
    'freelancer_only': [
        ('applied', 'Applied'),
        ('rejected', 'Rejected'),
        ('active', 'Active'),
        ('bookmarked', 'Bookmarked'), 
    ]
}

EXPERIENCE_LEVEL= (
    ('entry', 'Entry Level'),
    ('intermediate', 'Intermediate'),
    ('advanced', 'Advanced'),
    ('expert', 'Expert'),
)