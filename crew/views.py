from django.shortcuts import render
from crewai import Agent, Task, Crew, Process
from crewai.project import CrewBase, agent, crew, task
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Type
from crewai_tools import BaseTool
from django.conf import settings
from django.utils import timezone
from datetime import datetime
from meals.models import Meal, MealPlan, MealPlanMeal


class MealPlanItem(BaseModel):
    date: str
    meal_type: str
    meal_name: str
    nutritional_information: Optional[Dict[str, str]] = None  # Optional field

class MealPlanOutput(BaseModel):
    meals: List[MealPlanItem]


class MealQueryInputSchema(BaseModel):
    dietary_preference: Optional[str] = Field(None, description="Filter meals by dietary preference")
    meal_type: Optional[str] = Field(None, description="Filter meals by meal type")
    date_range_start: Optional[str] = Field(None, description="Start date for filtering meals")
    date_range_end: Optional[str] = Field(None, description="End date for filtering meals")

class FetchExistingMealsTool(BaseTool):
    name: str = "Fetch Existing Meals"
    description: str = "Tool to fetch existing meals from the database based on given criteria, which can be used in the meal planning process."
    args_schema: Type[BaseModel] = MealQueryInputSchema  # Ensure the type annotation is present

    def _run(self, dietary_preference: Optional[str], meal_type: Optional[str], date_range_start: Optional[str], date_range_end: Optional[str]) -> dict:
        # Convert date_range_start and date_range_end to datetime objects if provided
        if date_range_start:
            date_range_start = timezone.datetime.strptime(date_range_start, "%Y-%m-%d").date()
        if date_range_end:
            date_range_end = timezone.datetime.strptime(date_range_end, "%Y-%m-%d").date()

        # Build the query
        query = Meal.objects.all()

        if dietary_preference:
            query = query.filter(dietary_preference=dietary_preference)
        if date_range_start and date_range_end:
            query = query.filter(
                start_date__gte=date_range_start,
                start_date__lte=date_range_end
            )

        # Extract the relevant data
        meals_data = []
        for meal in query:
            meals_data.append({
                'name': meal.name,
                'description': meal.description,
                'price': meal.price,
                'start_date': meal.start_date.isoformat() if meal.start_date else None,
                'dietary_preference': meal.dietary_preference,
            })

        return {
            "status": "success",
            "meals": meals_data
        }

    def run(self, input_data: MealQueryInputSchema) -> dict:
        return self._run(
            dietary_preference=input_data.dietary_preference,
            meal_type=input_data.meal_type,
            date_range_start=input_data.date_range_start,
            date_range_end=input_data.date_range_end,
        )
    
@CrewBase
class SautaiAgentsCrew():
    """SautaiAgents crew"""
    agents_config = 'config/agents.yaml'
    tasks_config = 'config/tasks.yaml'
    llm_4o = ChatOpenAI(
        model='gpt-4o',
        api_key=settings.OPENAI_KEY,
	)

    llm = ChatOpenAI(
        model='gpt-4o-mini',
        api_key=settings.OPENAI_KEY,
        temperature=0.2,
	)
    
    def manager(self) -> Agent:
        return Agent(
			role='manager',
			goal='Oversee the entire meal planning process, ensuring that each task is completed accurately and on time. You will coordinate between the the crew to ensure a seamless workflow.',
			backstory="You're an experienced manager with a keen eye for detail. You ensure that all team members are working efficiently and effectively to deliver the best and complete meal planning service to the user.",
			allow_delegation=True,
            llm=self.llm,
        )


    @agent
    def shopping_list_generator(self) -> Agent:
        return Agent(
            config=self.agents_config['shopping_list_generator'],
            llm=self.llm,
            verbose=True
        )

    @agent
    def instruction_creator(self) -> Agent:
        return Agent(
            config=self.agents_config['instruction_creator'],
            llm=self.llm,
            verbose=True
        )

    @agent
    def newsletter_sender(self) -> Agent:
        return Agent(
            config=self.agents_config['newsletter_generator'],
            llm=self.llm_4o,
            verbose=True
        )
    

    @task
    def shopping_list_task(self) -> Task:
        return Task(
            config=self.tasks_config['shopping_list_task'],
            agent=self.shopping_list_generator(),
            output_file='shopping_list.txt',
            context= []
        )

    @task
    def instruction_creation_task(self) -> Task:
        return Task(
            config=self.tasks_config['instruction_creation_task'],
            agent=self.instruction_creator(),
            context= [self.shopping_list_task()]
        )
    
    @task
    def newsletter_task(self) -> Task:
        return Task(
            config=self.tasks_config['newsletter_task'],
            agent=self.newsletter_sender(),
            context= [self.instruction_creation_task()]
        )

    @crew
    def updated_crew(self) -> Crew:
        """Creates the SautaiAgents crew"""
        return Crew(
            agents=self.agents,  # Automatically created by the @agent decorator
            tasks=self.tasks,    # Automatically created by the @task decorator
            process=Process.hierarchical,  # or Process.hierarchical
            manager_agent=self.manager(),
        )

