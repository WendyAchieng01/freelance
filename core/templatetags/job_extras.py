from django import template

register = template.Library()

@register.filter
def remaining_attempts(job):
    return job.max_freelancers - job.responses.count()

@register.filter
def subtract(value, arg):
    """Subtracts the arg from the value"""
    return value - arg
