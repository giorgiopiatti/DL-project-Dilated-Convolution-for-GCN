from typing import Optional

from torch.utils.data import DataLoader

from torch_geometric.data.lightning_datamodule import LightningDataModule
from dilated_gnn_graphgym.loader.loader import create_loader
from torch_geometric.graphgym.checkpoint import get_ckpt_dir
from torch_geometric.graphgym.config import cfg
from torch_geometric.graphgym.imports import pl
from dilated_gnn_graphgym.train.logger import LoggerCallback
from torch_geometric.graphgym.model_builder import GraphGymModule
from pytorch_lightning.callbacks.early_stopping import EarlyStopping

from pytorch_lightning.strategies import DDPSpawnStrategy


class GraphGymDataModule(LightningDataModule):
    def __init__(self):
        self.loaders = create_loader()
        super().__init__(has_val=True, has_test=True)

    def train_dataloader(self) -> DataLoader:
        return self.loaders[0]

    def val_dataloader(self) -> DataLoader:
        # better way would be to test after fit.
        # First call trainer.fit(...) then trainer.test(...)
        return self.loaders[1]

    def test_dataloader(self) -> DataLoader:
        return self.loaders[2]

cfg.train.early_stopping = False
cfg.train.early_stopping_patience = 100
cfg.train.monitor_val = True
cfg.train.accumulate_grad = 1
cfg.train_strategy = None
cfg.train.compute_test = True
def train(model: GraphGymModule, datamodule, logger: bool = True,
          trainer_config: Optional[dict] = None):
    callbacks = []
    if logger:
        callbacks.append(LoggerCallback())

    if cfg.train.monitor_val:
        metric = f'val_{cfg.metric_best}'
    else:
        metric = cfg.metric_best

    if cfg.train.enable_ckpt:
        ckpt_cbk = pl.callbacks.ModelCheckpoint(dirpath=get_ckpt_dir(), monitor=metric, mode='max' if cfg.metric_agg == 'argmax' else 'min',
        save_last=True, auto_insert_metric_name=True)
        callbacks.append(ckpt_cbk)

    if cfg.train.early_stopping:
        cbk = EarlyStopping(monitor=metric, mode='max' if cfg.metric_agg == 'argmax' else 'min',
                            patience=cfg.train.early_stopping_patience)
        callbacks.append(cbk)                        

    trainer_config = trainer_config or {}
    strategy = None
    if cfg.train_strategy == 'ddp_spawn':
        strategy = DDPSpawnStrategy()
        
    trainer = pl.Trainer(
        **trainer_config,
        enable_checkpointing=cfg.train.enable_ckpt,
        callbacks=callbacks,
        default_root_dir=cfg.out_dir,
        max_epochs=cfg.optim.max_epoch,
        accelerator=cfg.accelerator,
        devices=cfg.devices,
        auto_select_gpus=True,
        accumulate_grad_batches=cfg.train.accumulate_grad,
        strategy=strategy
    )

    trainer.fit(model, datamodule=datamodule)
    if cfg.train.compute_test:
        trainer.test(model, datamodule=datamodule, ckpt_path='last')
        trainer.test(model, datamodule=datamodule, ckpt_path='best')
