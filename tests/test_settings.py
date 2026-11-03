import re
from uuid import uuid4

import pytest
from sqlalchemy import select

from conftest import PASSWORD
from james.assortment import entries, save_offer, save_product
from james.extensions import db
from james.models import (Category, Household, HouseholdItem, ItemSource, Membership, Product,
    PurchasePlan, PurchaseSource, ShoppingNeed, ShoppingView, User)
from james.services import change_item
from test_app import action, csrf, login, seed_item


def owner(app):
    with app.app_context():
        user = db.session.scalar(select(User).where(User.email == 'owner@example.test'))
        member = db.session.scalar(select(Membership).where(Membership.user_id == user.id))
        return member.household_id, member.id, user.id


def post(client, path, **data):
    return client.post(path, data={'csrf_token': csrf(client, '/'), **data})


def create_view(client, **data):
    return post(client, '/settings/shopping-views/new', name='Laufweg', scope='shared', item_sort='name', **data)


@pytest.mark.parametrize('path', ['/settings/', '/settings/profile', '/settings/household',
    '/settings/catalogue/category', '/settings/catalogue/source', '/settings/shopping-views', '/settings/shopping-views/new', '/settings/app'])
def test_owner_can_open_all_sections(app, client, path):
    seed_item(app)
    login(client)
    response = client.get(path, follow_redirects=True)
    assert response.status_code == 200
    assert 'Verwaltungsbereiche' in response.text and 'Einkaufsansichten' in response.text


def test_members_only_manage_their_profile_and_personal_views(app, client):
    seed_item(app)
    login(client, 'member@example.test')
    for path in ('/settings/profile','/settings/shopping-views','/settings/shopping-views/new'):
        assert client.get(path).status_code == 200
    for path in ('/settings/household','/settings/catalogue/category','/settings/catalogue/source','/settings/app','/catalogue','/household'):
        assert client.get(path).status_code == 403
    assert post(client, '/catalogue', kind='category', name='Forbidden').status_code == 403
    assert post(client, '/settings/shopping-views/new', name='Private',scope='personal',item_sort='name').status_code == 302
    assert create_view(client).status_code == 403


def test_last_owner_cannot_be_removed_or_demoted(app, client):
    home, member, user = owner(app)
    login(client)
    for changes in ({'action':'remove'}, {'action':'role','role':'member'}):
        response = post(client, f'/settings/members/{member}', version=1, **changes)
        assert response.status_code == 409
    with app.app_context():
        assert db.session.get(Membership,member).active
        assert db.session.get(Membership,member).role == 'owner'


def test_member_role_removal_and_restore_invalidate_old_sessions(app, client):
    home, _, _ = owner(app)
    login(client)
    second = app.test_client()
    login(second, 'member@example.test')
    with app.app_context():
        target = db.session.scalar(select(Membership).where(Membership.household_id == home, Membership.role == 'member'))
        identifier = target.id
    assert post(client,f'/settings/members/{identifier}',version=1,action='role',role='owner').status_code == 302
    assert second.get('/').status_code == 302
    login(second, 'member@example.test')
    assert post(client,f'/settings/members/{identifier}',version=2,action='remove').status_code == 302
    assert second.get('/').status_code == 302
    assert post(client,f'/settings/members/{identifier}',version=3,action='restore').status_code == 302
    with app.app_context():
        target=db.session.get(Membership, identifier)
        assert target.active and target.role == 'member'
    assert login(second,'member@example.test').status_code == 302


def test_member_and_catalogue_ids_are_household_scoped(app, client):
    _, _, _ = seed_item(app)
    foreign, foreign_home, _ = seed_item(app,'other@example.test')
    with app.app_context():
        member_id=db.session.scalar(select(Membership.id).where(Membership.household_id == foreign_home))
        cat_id=db.session.scalar(select(Category.id).where(Category.household_id == foreign_home))
    login(client)
    assert post(client,f'/settings/members/{member_id}',action='remove',version=1).status_code == 404
    assert post(client,'/settings/catalogue/category',action='retire',entry_id=cat_id,version=1).status_code == 404


def test_profile_preferences_apply_and_stale_forms_cannot_overwrite(app, client):
    home, _, user_id=owner(app)
    login(client)
    assert post(client,'/settings/app',version=1,layout='cards').status_code == 302
    assert 'data-layout="cards"' in client.get('/').text or 'layout=cards' in client.get('/').text
    assert post(client,'/settings/profile',action='profile',version=1,name='Neuer Name',layout='compact').status_code == 302
    assert 'layout=compact' in client.get('/').text
    assert post(client,'/settings/profile',action='profile',version=1,name='Stale',layout='cards').status_code == 409
    with app.app_context():
        assert db.session.get(User,user_id).name == 'Neuer Name'


def test_credentials_require_current_password_and_invalidate_other_sessions(app, client):
    login(client)
    other=app.test_client();login(other)
    response=post(client,'/settings/profile',action='credentials',version=1,email='changed@example.test',current_password='wrong',password='never-echo-this-password',password_confirm='never-echo-this-password')
    assert response.status_code == 400 and 'never-echo-this-password' not in response.text
    assert post(client,'/settings/profile',action='credentials',version=1,email='changed@example.test',current_password=PASSWORD,password='new-password-123456',password_confirm='new-password-123456').status_code == 302
    assert client.get('/settings/profile').status_code == 200
    assert other.get('/').status_code == 302


def test_unused_default_category_stays_deleted_after_new_article(app, client):
    _, home, _=seed_item(app);login(client)
    with app.app_context():
        entry=db.session.scalar(select(Category).where(Category.household_id==home,Category.name=='Pflege'));identifier=entry.id
    assert post(client,'/settings/catalogue/category',action='retire',entry_id=identifier,version=1).status_code == 302
    assert 'Pflege' not in client.get('/items/new').text
    assert post(client,'/items/new',name='Test',category='Vorrat',source='Laden',quantity=1).status_code == 302
    with app.app_context():
        assert db.session.get(Category,identifier) is None
        assert not db.session.scalar(select(Category.id).where(Category.household_id==home,Category.name=='Pflege'))


def test_used_category_deactivates_without_losing_articles_and_can_restore(app, client):
    item_id, home, _=seed_item(app);login(client)
    with app.app_context():
        item=db.session.get(HouseholdItem,item_id)
        entry=db.session.scalar(select(Category).where(Category.household_id==home,Category.name==item.category));identifier=entry.id
    assert post(client,'/settings/catalogue/category',action='retire',entry_id=identifier,version=1).status_code == 302
    with app.app_context():
        assert not db.session.get(Category,identifier).active
        assert db.session.get(HouseholdItem,item_id).name=='Kaffee'
    assert 'bisheriger Eintrag inaktiv' in client.get(f'/items/{item_id}/edit').text
    assert post(client,'/settings/catalogue/category',action='restore',entry_id=identifier,version=2).status_code == 302
    with app.app_context():
        assert db.session.get(Category,identifier).active


def test_source_with_historical_plan_is_not_deleted(app, client):
    item_id, home, _=seed_item(app);login(client)
    with app.app_context():
        source=db.session.scalar(select(PurchaseSource).where(PurchaseSource.household_id==home,PurchaseSource.name=='Coop'))
        identifier=source.id
        db.session.add(PurchasePlan(household_id=home,source_id=identifier,request_id=str(uuid4()),lines=[],state='closed'))
        db.session.commit()
    assert post(client,'/settings/catalogue/source',action='retire',entry_id=identifier,version=1).status_code == 302
    with app.app_context():
        assert db.session.get(PurchaseSource,identifier) is not None
        assert not db.session.get(PurchaseSource,identifier).active


def test_shared_and_personal_views_enforce_visibility_and_edit_rights(app, client):
    seed_item(app);login(client)
    assert create_view(client).status_code==302
    assert post(client,'/settings/shopping-views/new',name='Owner private',scope='personal',item_sort='name').status_code==302
    with app.app_context():
        shared=db.session.scalar(select(ShoppingView.id).where(ShoppingView.user_id.is_(None)))
        private=db.session.scalar(select(ShoppingView.id).where(ShoppingView.user_id.is_not(None)))
    member=app.test_client();login(member,'member@example.test')
    assert 'Owner private' not in member.get('/settings/shopping-views').text
    assert member.get(f'/settings/shopping-views/{private}').status_code==403
    assert member.get(f'/shopping?view_id={private}').status_code==404
    assert post(member,f'/settings/shopping-views/{shared}',action='delete',version=1).status_code==403
    assert member.get(f'/shopping?view_id={shared}').status_code==200


def test_saved_view_filters_orders_groups_and_keeps_unknown_groups_visible(app, client):
    first, home, _=seed_item(app);login(client)
    with app.app_context():
        cats=entries(home,'category');ids={cat.name:cat.id for cat in cats}
        for i,category in enumerate(('Frisches','Pflege','Vorrat')):
            item=HouseholdItem(household_id=home,name=f'Produkt {i}',category=category,source='Laden')
            db.session.add(item);db.session.flush();db.session.add(ShoppingNeed(item_id=item.id,quantity=1))
        db.session.commit()
    assert create_view(client,category_order=[ids['Pflege'],ids['Frisches']]).status_code==302
    with app.app_context():view_id=db.session.scalar(select(ShoppingView.id))
    html=client.get(f'/shopping?view_id={view_id}').text
    groups=re.findall(r'class="shopping-group"><h2>([^<]+)',html)
    assert groups==['Pflege','Frisches','Vorrat']
    assert post(client,f'/settings/shopping-views/{view_id}',name='Nur frisch',scope='shared',item_sort='name',version=1,category_ids=[ids['Frisches']],category_order=[ids['Pflege'],ids['Frisches']]).status_code==302
    html=client.get(f'/shopping?view_id={view_id}').text
    assert re.findall(r'class="shopping-group"><h2>([^<]+)',html)==['Frisches']
    assert '2 Artikel durch den Warengruppenfilter' in html
    assert 'name="view_id" value="'+str(view_id)+'"' in html
    with app.app_context():assert sum(db.session.scalars(select(ShoppingNeed.quantity)))==3


def test_view_rejects_foreign_categories_invalid_sorts_and_stale_versions(app, client):
    seed_item(app);_,foreign_home,_=seed_item(app,'other@example.test');login(client)
    with app.app_context():cat=db.session.scalar(select(Category.id).where(Category.household_id==foreign_home))
    assert create_view(client,category_order=[cat]).status_code==400
    assert post(client,'/settings/shopping-views/new',name='bad',scope='personal',item_sort='bad').status_code==400
    assert create_view(client).status_code==302
    with app.app_context():identifier=db.session.scalar(select(ShoppingView.id))
    assert post(client,f'/settings/shopping-views/{identifier}',action='delete',version=99).status_code==409


def test_per_source_defaults_prioritize_personal_and_explicit_clear(app, client):
    _,home,_=seed_item(app);login(client)
    with app.app_context():source=db.session.scalar(select(PurchaseSource.id).where(PurchaseSource.household_id==home,PurchaseSource.name=='Laden'))
    assert create_view(client,source_id=source,is_default='1').status_code==302
    assert post(client,'/settings/shopping-views/new',name='Persönlich',scope='personal',item_sort='name',source_id=source,is_default='1').status_code==302
    with app.app_context():personal=db.session.scalar(select(ShoppingView.id).where(ShoppingView.user_id.is_not(None)))
    html=client.get('/shopping?source=Laden').text
    assert 'Ansicht: <strong>Persönlich' in html
    assert 'Ansicht: <strong>' not in client.get('/shopping?source=Laden&view_id=0').text
    # Only one default per scope and location.
    assert post(client,'/settings/shopping-views/new',name='Neuer Standard',scope='personal',item_sort='name',source_id=source,is_default='1').status_code==302
    with app.app_context():assert not db.session.get(ShoppingView,personal).is_default


def test_category_merge_preserves_view_ids_and_item_versions(app, client):
    item_id,home,_=seed_item(app);login(client)
    with app.app_context():
        original=db.session.scalar(select(Category).where(Category.household_id==home,Category.name=='Sonstiges'))
        target=db.session.scalar(select(Category).where(Category.household_id==home,Category.name=='Vorrat'))
        old_id,new_id=original.id,target.id
    assert create_view(client,category_order=[old_id,new_id],category_ids=[old_id]).status_code==302
    assert post(client,'/settings/catalogue/category',action='retire',entry_id=old_id,version=1,replacement_id=new_id).status_code==302
    with app.app_context():
        item=db.session.get(HouseholdItem,item_id);view=db.session.scalar(select(ShoppingView))
        assert item.category=='Vorrat' and item.version==2
        assert view.category_order==[new_id] and view.category_ids==[new_id]
        assert not db.session.get(Category,old_id).active


def test_view_defaults_clear_when_a_shared_view_becomes_private_or_is_deleted(app, client):
    _,home,user_id=seed_item(app);login(client)
    assert create_view(client).status_code==302
    with app.app_context():
        view=db.session.scalar(select(ShoppingView));identifier=view.id
        household=db.session.get(Household,home);household.settings={'default_view_id':identifier}
        other=db.session.scalar(select(User).where(User.email=='member@example.test'))
        other.preferences={'default_view_id':identifier}
        db.session.commit()
    assert post(client,f'/settings/shopping-views/{identifier}',version=1,name='Nu privé',scope='personal',item_sort='name').status_code==302
    with app.app_context():
        assert db.session.get(Household,home).settings.get('default_view_id') is None
        assert db.session.scalar(select(User).where(User.email=='member@example.test')).preferences.get('default_view_id') is None
    assert post(client,f'/settings/shopping-views/{identifier}',version=2,action='delete').status_code==302
    with app.app_context():assert db.session.get(ShoppingView,identifier) is None


def test_deactivated_category_does_not_prevent_new_stock_actions_and_undo(app, client):
    item_id,home,_=seed_item(app);login(client)
    with app.app_context():
        identifier=db.session.scalar(select(Category.id).where(Category.household_id==home,Category.name=='Sonstiges'))
    assert post(client,'/settings/catalogue/category',action='retire',entry_id=identifier,version=1).status_code==302
    result=action(client,item_id,'replenish',2)
    assert result.status_code==302
    event_id=re.search(r'undo=(\d+)',result.location).group(1)
    assert post(client,f'/activity/{event_id}/undo',version=3,request_id=str(uuid4())).status_code==302


def test_source_merge_retains_historical_plan_and_invalidates_secondary_source_edit(app, client):
    item_id,home,_=seed_item(app);login(client)
    with app.app_context():
        coop=db.session.scalar(select(PurchaseSource).where(PurchaseSource.household_id==home,PurchaseSource.name=='Coop'))
        migros=db.session.scalar(select(PurchaseSource).where(PurchaseSource.household_id==home,PurchaseSource.name=='Migros'))
        old_id,target_id=coop.id,migros.id
        db.session.add(ItemSource(item_id=item_id,source_id=old_id))
        plan=PurchasePlan(household_id=home,source_id=old_id,request_id=str(uuid4()),lines=[],state='closed')
        db.session.add(plan);db.session.commit();plan_id=plan.id
    assert post(client,'/settings/catalogue/source',action='retire',entry_id=old_id,version=1,replacement_id=target_id).status_code==302
    with app.app_context():
        assert db.session.get(PurchasePlan,plan_id).source_id==old_id
        assert db.session.get(ItemSource,(item_id,target_id))
        assert not db.session.get(ItemSource,(item_id,old_id))
        assert db.session.get(HouseholdItem,item_id).version==2


def test_two_owners_cannot_concurrently_remove_the_last_administrator(app):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from flask import g
    from james.administration import change_member
    with app.app_context():
        if db.engine.dialect.name!='postgresql':pytest.skip('Requires row locks in the isolated Postgres suite.')
        members=db.session.scalars(select(Membership).where(Membership.household_id==owner(app)[0])).all()
        for member in members:member.role='owner'
        db.session.commit();targets=[(member.id,member.version,member.household_id) for member in members]
    barrier=Barrier(2)
    def demote(target):
        identifier,version,home=target
        with app.app_context():
            g.household=db.session.get(Household,home)
            g.membership=db.session.get(Membership,identifier)
            barrier.wait(timeout=10)
            try:
                change_member(identifier,'role',version,'member');db.session.commit();return 'saved'
            except ValueError:
                db.session.rollback();return 'conflict'
    with ThreadPoolExecutor(max_workers=2) as executor:results=list(executor.map(demote,targets))
    assert sorted(results)==['conflict','saved']
    with app.app_context():assert len(db.session.scalars(select(Membership).where(Membership.household_id==targets[0][2],Membership.role=='owner',Membership.active.is_(True))).all())==1


def test_shopping_actions_and_undo_preserve_saved_view_context(app, client):
    item_id,home,_=seed_item(app);login(client)
    assert action(client,item_id,'extra',1,quantity=2).status_code==302
    assert create_view(client).status_code==302
    with app.app_context():view_id=db.session.scalar(select(ShoppingView.id))
    response=post(client,f'/items/{item_id}/action',action='purchase',version=2,quantity=1,
        request_id=str(uuid4()),return_to='shopping',view_id=view_id)
    assert response.status_code==302 and f'view_id={view_id}' in response.location
    event_id=re.search(r'undo=(\d+)',response.location).group(1)
    response=post(client,f'/activity/{event_id}/undo',version=3,request_id=str(uuid4()),return_to='shopping',view_id=view_id)
    assert response.status_code==302 and f'view_id={view_id}' in response.location
    with app.app_context():assert db.session.get(ShoppingNeed,item_id).quantity==2


def test_source_merge_rejects_overlapping_offers_without_partial_changes(app, client):
    from james.models import ShopOffer
    item_id,home,_=seed_item(app);login(client)
    with app.app_context():
        sources=entries(home,'source');old,target=sources[:2];old_id,target_id=old.id,target.id
        product=save_product(home,item_id,{'product_name':'Kaffeepackung'})
        save_offer(home,item_id,product.id,{'source_id':old_id,'units_per_pack':'1'})
        save_offer(home,item_id,product.id,{'source_id':target_id,'units_per_pack':'1'})
        db.session.commit()
    response=post(client,'/settings/catalogue/source',action='retire',entry_id=old_id,version=1,replacement_id=target_id)
    assert response.status_code==409
    with app.app_context():
        assert db.session.get(PurchaseSource,old_id).active
        assert set(db.session.scalars(select(ShopOffer.source_id)))=={old_id,target_id}


def test_chained_catalogue_merges_keep_old_labels_resolvable(app, client):
    from james.assortment import resolve
    _,home,_=seed_item(app);login(client)
    with app.app_context():
        categories=entries(home,'category');a,b,c=categories[:3]
        aid,bid,cid,old_name=a.id,b.id,c.id,a.name
    assert post(client,'/settings/catalogue/category',action='retire',entry_id=aid,version=1,replacement_id=bid).status_code==302
    assert post(client,'/settings/catalogue/category',action='retire',entry_id=bid,version=1,replacement_id=cid).status_code==302
    assert post(client,'/settings/catalogue/category',action='retire',entry_id=cid,version=1).status_code==302
    with app.app_context():
        assert db.session.get(Category,cid) is not None
        assert resolve(home,'category',old_name).id==cid


def test_history_only_catalogue_reference_uses_unicode_alias_keys(app, client):
    from james.models import Activity
    item_id,home,user_id=seed_item(app);login(client)
    assert post(client,'/settings/catalogue/category',action='save',name='Bu\ufb01').status_code==302
    with app.app_context():
        identifier=db.session.scalar(select(Category.id).where(Category.household_id==home,Category.name=='Bu\ufb01'))
        db.session.add(Activity(household_id=home,item_id=item_id,user_id=user_id,request_id=str(uuid4()),
            action='edit',before_state={'category':'Bu\ufb01'},after_state={},version_after=1))
        db.session.commit()
    assert post(client,'/settings/catalogue/category',action='retire',entry_id=identifier,version=1).status_code==302
    with app.app_context():assert not db.session.get(Category,identifier).active


def test_inactive_view_source_requires_explicit_reassignment(app, client):
    _,home,_=seed_item(app);login(client)
    with app.app_context():source_id=entries(home,'source')[0].id
    assert create_view(client,source_id=source_id).status_code==302
    with app.app_context():identifier=db.session.scalar(select(ShoppingView.id))
    assert post(client,'/settings/catalogue/source',action='retire',entry_id=source_id,version=1).status_code==302
    assert post(client,f'/settings/shopping-views/{identifier}',version=1,name='Edited',scope='shared',item_sort='name').status_code==400
    assert post(client,f'/settings/shopping-views/{identifier}',version=1,name='Alle Orte',scope='shared',item_sort='name',source_id='').status_code==302
    with app.app_context():assert db.session.get(ShoppingView,identifier).source_id is None
