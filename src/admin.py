from sqladmin import ModelView
from src.models import Lead


class LeadAdmin(ModelView, model=Lead):
    column_list = ["id", "phone"]
    column_searchable_list = ["phone"]

    name = "Lead"
    name_plural = "Leads"
    icon = "fa fa-user"
