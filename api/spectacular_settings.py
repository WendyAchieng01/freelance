# api/spectacular_settings.py
from accounts.models import Profile, FreelancerProfile, ClientProfile

ENUM_NAME_OVERRIDES = {
    'UserTypeEnum': Profile._meta.get_field('user_type').choices,
    'AvailabilityEnum': FreelancerProfile._meta.get_field('availability').choices,
    'IndustryEnum': ClientProfile._meta.get_field('industry').choices,
    'PreferredFreelancerLevelEnum': ClientProfile._meta.get_field('preferred_freelancer_level').choices,
    'PayIdEnum': Profile._meta.get_field('pay_id').choices,
}
