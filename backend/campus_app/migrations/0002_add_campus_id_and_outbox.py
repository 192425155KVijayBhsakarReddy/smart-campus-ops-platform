from django.db import migrations, models
import uuid

class Migration(migrations.Migration):

    dependencies = [
        ('campus_app', '0001_initial'),
    ]

    operations = [
        # 1. Expand Booking schema with campus_id (default 'CAMPUS-ENG') for backward compatibility
        migrations.AddField(
            model_name='booking',
            name='campus_id',
            field=models.CharField(db_index=True, default='CAMPUS-ENG', max_length=32),
        ),

        # 2. Expand Room schema with campus_id
        migrations.AddField(
            model_name='room',
            name='campus_id',
            field=models.CharField(db_index=True, default='CAMPUS-ENG', max_length=32),
        ),

        # 3. Create durable OutboxIntent model for asynchronous resilience
        migrations.CreateModel(
            name='OutboxIntent',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('intent_id', models.CharField(db_index=True, max_length=64, unique=True)),
                ('event_type', models.CharField(max_length=64)),
                ('payload', models.JSONField()),
                ('status', models.CharField(choices=[('PENDING_RETRY', 'Pending Retry'), ('PROCESSED', 'Processed'), ('DEAD_LETTER', 'Dead Letter')], db_index=True, default='PENDING_RETRY', max_length=32)),
                ('retry_count', models.PositiveIntegerField(default=0)),
                ('next_retry_at', models.FloatField(default=0.0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('processed_at', models.DateTimeField(blank=True, null=True)),
            ],
            options={
                'ordering': ['created_at'],
            },
        ),
    ]
