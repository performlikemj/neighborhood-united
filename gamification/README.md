# Django Gamification App

A Django application for adding gamification features to the Hood United platform. This app provides a complete backend for tracking user progress, awarding points, managing achievements, and tracking streaks for meal planning activities.

## Features

- **Point System**: Track and award points for user activities
- **Levels**: Users level up as they earn points
- **Achievements**: Unlock badges and achievements based on various criteria
- **Streaks**: Track consecutive daily activity (meal planning)
- **Weekly Goals**: Set and track progress toward weekly meal planning goals
- **Leaderboard**: Compare progress with other users
- **Analytics**: Track gamification events for analysis

### Level Tiers

User levels map to fun chef-themed titles that appear in the API responses:

| Level Range | Title |
|-------------|-------|
| 1-4         | Dish Washer |
| 5-9         | Sous Chef |
| 10+         | Head Chef |

## Installation

The app is installed as part of the main Hood United project. Make sure it's included in your `INSTALLED_APPS` in settings.py:

```python
INSTALLED_APPS = [
    # ... other apps
    'gamification',
]
```

Add the gamification URLs to your main urls.py:

```python
urlpatterns = [
    # ... other URL patterns
    path('gamification/', include('gamification.urls')),
]
```

Run migrations to create the necessary database tables:

```bash
python manage.py makemigrations
python manage.py migrate
```

## Initial Setup

Create initial achievements by running the provided management command:

```bash
python manage.py create_achievements
```

This will create a set of default achievements for points, streaks, and meal planning milestones.

## API Endpoints

The gamification app provides the following API endpoints:

- `/gamification/api/profile/` - Get the user's gamification profile
- `/gamification/api/leaderboard/` - Get the current leaderboard
- `/gamification/api/achievements/` - List all achievements and user progress
- `/gamification/api/points-history/` - Get a user's points transaction history
- `/gamification/api/streamlit-data/` - Get data formatted for Streamlit UI integration

All endpoints require authentication and return JSON responses.

## Models

- **UserProfile** - Extended profile for gamification stats (points, level, streak)
- **Achievement** - Defines achievements and their criteria
- **UserAchievement** - Records which achievements users have earned
- **WeeklyGoal** - Tracks weekly meal planning goals
- **PointsTransaction** - Records point transactions (earned/spent)
- **AnalyticsEvent** - Records gamification events for analytics

## Integration with Streamlit

The app includes a `streamlit_integration.py` file that provides example code for integrating with a Streamlit front-end. This file demonstrates how to:

1. Connect to the Django backend API
2. Fetch gamification data
3. Update Streamlit session state
4. Display gamification elements in the Streamlit UI

See the file for detailed examples.

## Development

### Adding New Achievement Types

To add new achievement types:

1. Update the `Achievement` model if needed with new criteria fields
2. Modify the `check_achievements` function in `services.py` to check for the new criteria
3. Add any necessary signal handlers in `signals.py` to trigger achievement checks

### Point System

The app uses a unified point system defined in `services.py` as `UNIFIED_EVENT_POINTS`. Points are organized by engagement level:

```python
UNIFIED_EVENT_POINTS = {
    # Basic engagement (1-5 points) - Daily activities
    'login': 2,
    'streak_update': 1,
    'meal_planned': 3,
    'cooking_instructions_generated': 2,
    
    # Active participation (5-15 points) - Meaningful interactions
    'review': 8,
    'meal_reviewed': 8,
    'meal_plan_reviewed': 10,
    'meals_updated': 5,
    'chef_connect': 12,
    'cooking': 15,
    
    # Major actions (15-25 points) - Significant platform activities
    'meal_plan_approved': 20,
    'replaced_with_chef_meal': 18,
    'achievement': 15,
    'level_up': 25,
    
    # Major milestones (50+ points) - Weekly/rare achievements
    'goal_completed': 100,
}
```

This unified system ensures consistent point values across all gamification events and maintains logical hierarchy between different activity types.

## Contributing

If you want to contribute to this app, please consider the following guidelines:

1. Use Django signals to integrate with other apps
2. Keep gamification logic in the `services.py` module
3. Add unit tests for new features
4. Document any changes to the API endpoints

## License

This app is part of the Hood United project and follows the same licensing terms. 