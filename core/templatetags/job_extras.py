from django import template

register = template.Library()

@register.filter
def remaining_attempts(job):
    return job.max_freelancers - job.responses.count()